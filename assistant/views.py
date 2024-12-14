# assistant/views.py

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .forms import QuestionForm
from .models import Conversation, Message
from .shopify_chat_cli import (
    get_product_info_by_sku,
    update_product_by_sku,
    create_product_with_sku,
    create_products_from_csv,
    update_products_from_csv,
    put_product_on_sale,
    take_product_off_sale,
    disable_product_by_sku,
)
from environs import Env
import requests
import json, os
import csv
from io import TextIOWrapper
from openai import OpenAI
from django.conf import settings

env = Env()
env.read_env()

DEBUG = True

OPENAI_API_KEY = env("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

MODEL = "gpt-4o-mini"
MAX_LEN = 1800
MAX_TOKENS = 300

PROMPT = """Answer the question based on the context below."""

tools = [
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send an email to one or more recipients",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipients": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "A list of email addresses to send the message to"
                    },
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["recipients", "subject", "body"],
            },
        }
    },
    {
    "type": "function",
    "function": {
            "name": "get_product_info_by_sku",
            "description": "Retrieve product information by SKU, including cost.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string", "description": "The SKU of the product variant"},
                    "fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "A list of specific fields to return (optional). Possible fields: ['sku', 'title', 'price', 'compare_at_price', 'cost', 'available', 'vendor', 'product_type', 'tags', 'body_html']"
                    }
                },
                "required": ["sku"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_product_by_sku",
            "description": "Update product fields by SKU. Only provided fields will be updated.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string", "description": "The SKU of the product to update"},
                    "title": {"type": "string", "description": "The new title of the product"},
                    "product_type": {"type": "string", "description": "The new product type"},
                    "vendor": {"type": "string", "description": "The new vendor name"},
                    "tags": {"type": "string", "description": "Comma-separated tags"},
                    "body_html": {"type": "string", "description": "Product description in HTML"},
                    "price": {"type": "string", "description": "The new variant price"},
                    "compare_at_price": {"type": "string", "description": "The new compare at price"},
                    "cost": {"type": "string", "description": "The new cost of goods"},
                    "available": {"type": "integer", "description": "The new available quantity"}
                },
                "required": ["sku"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_product_with_sku",
            "description": "Create a new product with a given SKU. Other fields are optional.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string", "description": "The SKU of the new product variant"},
                    "title": {"type": "string", "description": "The title of the product"},
                    "product_type": {"type": "string", "description": "The product type"},
                    "vendor": {"type": "string", "description": "The vendor name"},
                    "tags": {"type": "string", "description": "Comma-separated tags"},
                    "body_html": {"type": "string", "description": "Product description in HTML"},
                    "price": {"type": "string", "description": "The variant price"},
                    "compare_at_price": {"type": "string", "description": "The compare at price"},
                    "cost": {"type": "string", "description": "The cost of goods"},
                    "available": {"type": "integer", "description": "The available quantity"}
                },
                "required": ["sku"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "put_product_on_sale",
            "description": "Put a product variant on sale by SKU",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string", "description": "The SKU of the product variant"},
                    "sale_price": {"type": "string", "description": "The discounted sale price"},
                    "regular_price": {"type": "string", "description": "The original regular price"},
                    "tags_to_add": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags to add to the product, e.g. ['on-sale']"
                    },
                },
                "required": ["sku", "sale_price", "regular_price"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "take_product_off_sale",
            "description": "Remove the sale pricing from a product variant by SKU and restore original price",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string", "description": "The SKU of the product variant"},
                    "tags_to_remove": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags to remove from the product, e.g. ['on-sale']"
                    },
                },
                "required": ["sku"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "disable_product_by_sku",
            "description": "Disable a product variant by SKU. Sets title, product_type, tags, body_html and variant.inventory_policy to indicate unavailability.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string", "description": "The SKU of the product to disable"}
                },
                "required": ["sku"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_products_from_csv",
            "description": "Create multiple products from a CSV file. The CSV must have a 'sku' column.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "The name of the CSV file (temp file)."}
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_products_from_csv",
            "description": "Update multiple existing products from a CSV file by SKU.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "The name of the CSV file (temp file)."}
                },
                "required": ["filename"]
            }
        }
    },
]

def send_email(recipients, subject, body, attachment=None):
    mailgun_domain = env("MAILGUN_DOMAIN")
    mailgun_api_key = env("MAILGUN_API_KEY")
    from_email = env("FROM_EMAIL")

    # Mailgun can accept a list of recipients directly
    data = {
        "from": from_email,
        "to": recipients,  # <-- This is now a list
        "subject": subject,
        "text": body,
    }

    files = []
    if attachment:
        attachment.seek(0)
        file_content = attachment.read()
        files.append(
            ("attachment", (attachment.name, file_content, "application/octet-stream"))
        )

    try:
        response = requests.post(
            f"https://api.mailgun.net/v3/{mailgun_domain}/messages",
            auth=("api", mailgun_api_key),
            data=data,
            files=files if files else None
        )
        response.raise_for_status()
        return {"status": "success", "details": response.json()}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "details": str(e)}

def answer_question(
    model=MODEL,
    question="What is your store phone number?",
    max_len=MAX_LEN,
    debug=False,
    max_tokens=MAX_TOKENS,
    uploaded_file=None,
    csv_filename=None,
    apply_time=None,
    revert_time=None,
    attachment_path=None,
):
    # If apply_time is given by the form and user requested scheduling:
    if apply_time and csv_filename:
        from assistant.tasks import apply_csv_updates, revert_csv_updates
        import uuid
        batch_id = str(uuid.uuid4())
        
        apply_csv_updates.apply_async(args=[csv_filename, batch_id], eta=apply_time)
        scheduling_message = f"Your CSV updates have been scheduled at {apply_time}."
        
        if revert_time:
            revert_csv_updates.apply_async(args=[batch_id], eta=revert_time)
            scheduling_message += f" They will be reverted at {revert_time}."
        
        return scheduling_message

    context = ""
    if debug:
        print("Context:\n" + context)

    try:
        prompt = f"""{PROMPT}```Context: {context}```\n\n---\n\n``Question: {question}```\n Answer:"""
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": """You are a helpful assistant for the music store All You Need Music. 
                    You can send emails and interact with Shopify products using the provided functions.
                    When the user asks to email an attached file, assume that one is provided by the user form.
                    Call the `send_email` function with the given recipient, subject, and body. The backend 
                    code will handle the attachment automatically. When the user asks to create or update products 
                    from an attached CSV, call `create_products_from_csv` or `update_products_from_csv` with a
                    dummy filename (e.g., "attached.csv"). The backend code will replace that with the actual 
                    uploaded CSV file.""",
                },
                {"role": "user", "content": prompt},
            ],
            model=model,
            tools=tools,
            temperature=0,
        )

        message = response.choices[0].message
        answer = message.content if message.content else ""
    
        # Handle tool calls
        if message.tool_calls:
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)

                if tool_name == "send_email":
                    recipients = args["recipients"]
                    subject = args["subject"]
                    body = args["body"]

                    # If apply_time is provided, schedule the email
                    if apply_time:
                        from assistant.tasks import send_scheduled_email
                        # Use the attachment_path if available
                        # Note: attachment_path must be known or passed into answer_question
                        # You might pass it in similarly to how you pass csv_filename.
                        send_scheduled_email.apply_async(
                            args=[recipients, subject, body, attachment_path],
                            eta=apply_time
                        )
                        answer += (
                            f"\n\nYour email has been scheduled at {apply_time}!\n"
                            f"Recipients: {recipients}\n"
                            f"Subject: {subject}\n"
                            f"Body: {body}"
                        )
                        if uploaded_file:
                            answer += f"\nAttachment scheduled: {uploaded_file.name}"
                    else:
                        # No scheduling, send immediately
                        email_response = send_email(
                            recipients, subject, body,
                            attachment=uploaded_file if uploaded_file else None
                        )
                        if email_response["status"] == "success":
                            answer += (
                                "\n\nEmail was successfully sent!\n"
                                f"Recipients: {recipients}\n"
                                f"Subject: {subject}\n"
                                f"Body: {body}"
                            )
                            if uploaded_file:
                                answer += f"\nAttachment: {uploaded_file.name}"
                        else:
                            answer += f"\n\nFailed to send email.\nError: {email_response['details']}"

                elif tool_name == "get_product_info_by_sku":
                    product_info = get_product_info_by_sku(args["sku"])
                    # Print JSON for debugging
                    print("Product Info JSON for debugging:", json.dumps(product_info, indent=2))
                
                    requested_fields = args.get("fields", None)  # fields is optional
                    if requested_fields:
                        # Filter product_info to only include requested fields
                        filtered_info = {field: product_info.get(field, 'N/A') for field in requested_fields}
                        answer += "\n\nRequested Product Information:\n"
                        for f, val in filtered_info.items():
                            answer += f"{f.capitalize()}: {val}\n"
                    else:
                        # Show all fields
                        answer += (
                            "\n\nProduct Information:\n"
                            f"SKU: {product_info.get('sku', 'Unknown')}\n"
                            f"Title: {product_info.get('title', 'No title')}\n"
                            f"Price: {product_info.get('price', 'N/A')}\n"
                            f"Compare at Price: {product_info.get('compare_at_price', 'N/A')}\n"
                            f"Cost: {product_info.get('cost', 'N/A')}\n"
                            f"Available Quantity: {product_info.get('available', 'N/A')}\n"
                            f"Vendor: {product_info.get('vendor', 'N/A')}\n"
                            f"Type: {product_info.get('product_type', 'N/A')}\n"
                            f"Tags: {product_info.get('tags', '')}\n"
                            "Description:\n"
                            f"{product_info.get('body_html', 'No description')}"
                        )

                elif tool_name == "update_product_by_sku":
                    update_fields = {k: v for k, v in args.items() if k != "sku"}
                    update_response = update_product_by_sku(args["sku"], update_fields)
                    # Print JSON for debugging
                    print("Update Product Response JSON for debugging:", json.dumps(update_response, indent=2))

                    if update_response.get("status") == "success":
                        updated_info = update_response.get("updated_fields", {})
                        answer += (
                            "\n\nProduct successfully updated!\n"
                            f"SKU: {updated_info.get('sku', args['sku'])}\n"
                            f"Title: {updated_info.get('title', 'No title')}\n"
                            f"Price: {updated_info.get('price', 'N/A')}\n"
                            f"Compare at Price: {updated_info.get('compare_at_price', 'N/A')}\n"
                            f"Available Quantity: {updated_info.get('available', 'N/A')}\n"
                            f"Vendor: {updated_info.get('vendor', 'N/A')}\n"
                            f"Type: {updated_info.get('product_type', 'N/A')}\n"
                            f"Tags: {updated_info.get('tags', '')}\n"
                            "Description:\n"
                            f"{updated_info.get('body_html', 'No description')}"
                        )
                    else:
                        error_message = update_response.get("message", "Unknown error")
                        answer += f"\n\nFailed to update product.\nError: {error_message}"

                elif tool_name == "create_product_with_sku":
                    create_fields = {k: v for k, v in args.items() if k != "sku"}
                    create_response = create_product_with_sku(args["sku"], **create_fields)
                    # Print JSON for debugging
                    print("Create Product Response JSON for debugging:", json.dumps(create_response, indent=2))

                    if create_response.get("status") == "success":
                        product_info = create_response.get("product_info", {})
                        answer += (
                            "\n\nProduct successfully created!\n"
                            f"SKU: {product_info.get('sku', args['sku'])}\n"
                            f"Title: {product_info.get('title', 'No title')}\n"
                            f"Price: {product_info.get('price', 'N/A')}\n"
                            f"Compare at Price: {product_info.get('compare_at_price', 'N/A')}\n"
                            f"Available Quantity: {product_info.get('available', 'N/A')}\n"
                            f"Vendor: {product_info.get('vendor', 'N/A')}\n"
                            f"Type: {product_info.get('product_type', 'N/A')}\n"
                            f"Tags: {product_info.get('tags', '')}\n"
                            "Description:\n"
                            f"{product_info.get('body_html', 'No description')}"
                        )
                    else:
                        error_message = create_response.get("message", "Unknown error")
                        answer += f"\n\nFailed to create product.\nError: {error_message}"
                        
                elif tool_name == "create_products_from_csv":
                    if csv_filename:
                        create_response = create_products_from_csv(csv_filename)
                        # Print JSON to console for debugging
                        print("Create Products From CSV Response JSON:", json.dumps(create_response, indent=2))
                        
                        if create_response.get("status") == "success":
                            created_products = create_response.get("created_products", [])
                            product_list = "\n".join([f"- {p.get('sku', 'Unknown SKU')} ({p.get('title', 'No title')})" for p in created_products])
                            
                            answer += (
                                "\n\nProducts were successfully created!\n"
                                f"Number of products created: {len(created_products)}\n"
                                f"Created Products:\n{product_list}"
                            )
                        else:
                            # Handle error scenario
                            error_details = create_response.get("details", "Unknown error")
                            answer += f"\n\nFailed to create products from CSV.\nError: {error_details}"
                    else:
                        answer += "\n\nError: No CSV file provided."
                
                elif tool_name == "update_products_from_csv":
                    if csv_filename:
                        update_response = update_products_from_csv(csv_filename)
                        # Print JSON to console for debugging
                        print("Update Products From CSV Response JSON:", json.dumps(update_response, indent=2))
                        
                        if update_response.get("status") == "success":
                            updated_products = update_response.get("updated_products", [])
                            product_list = "\n".join([f"- {p.get('sku', 'Unknown SKU')} ({p.get('title', 'No title')})" for p in updated_products])
                            
                            answer += (
                                "\n\nProducts were successfully updated!\n"
                                f"Number of products updated: {len(updated_products)}\n"
                                f"Updated Products:\n{product_list}"
                            )
                        else:
                            # Handle error scenario
                            error_details = update_response.get("details", "Unknown error")
                            answer += f"\n\nFailed to update products from CSV.\nError: {error_details}"
                    else:
                        answer += "\n\nError: No CSV file provided."

                elif tool_name == "put_product_on_sale":
                    sku = args["sku"]
                    sale_price = args["sale_price"]
                    regular_price = args["regular_price"]
                    tags_to_add = args.get("tags_to_add", ["on-sale"])
                    sale_response = put_product_on_sale(sku, sale_price, regular_price, tags_to_add)

                    # Print JSON to console for debugging
                    print("Put Product On Sale Response JSON:", json.dumps(sale_response, indent=2))

                    if sale_response.get("status") == "success":
                        # Retrieve updated product info
                        try:
                            updated_info = get_product_info_by_sku(sku)
                            answer += (
                                "\n\nProduct successfully put on sale!\n"
                                f"SKU: {updated_info.get('sku', sku)}\n"
                                f"Title: {updated_info.get('title', 'No title')}\n"
                                f"New Price: {updated_info.get('price', 'N/A')} (was {regular_price}, now {sale_price})\n"
                                f"Compare at Price: {updated_info.get('compare_at_price', 'N/A')}\n"
                                f"Available Quantity: {updated_info.get('available', 'N/A')}\n"
                                f"Vendor: {updated_info.get('vendor', 'N/A')}\n"
                                f"Type: {updated_info.get('product_type', 'N/A')}\n"
                                f"Tags: {updated_info.get('tags', '')}\n"
                                "Description:\n"
                                f"{updated_info.get('body_html', 'No description')}"
                            )
                        except Exception as e:
                            answer += (
                                "\n\nProduct put on sale successfully, but unable to retrieve updated product info.\n"
                                f"SKU: {sku}\n"
                                f"Error: {str(e)}"
                            )
                    else:
                        error_message = sale_response.get("message", "Unknown error")
                        answer += f"\n\nFailed to put product on sale.\nError: {error_message}"

                elif tool_name == "take_product_off_sale":
                    sku = args["sku"]
                    tags_to_remove = args.get("tags_to_remove", ["on-sale"])
                    off_sale_response = take_product_off_sale(sku, tags_to_remove)

                    # Print JSON for debugging
                    print("Take Product Off Sale Response JSON:", json.dumps(off_sale_response, indent=2))

                    if off_sale_response.get("status") == "success":
                        # Retrieve updated product info
                        try:
                            updated_info = get_product_info_by_sku(sku)
                            answer += (
                                "\n\nProduct successfully taken off sale!\n"
                                f"SKU: {updated_info.get('sku', sku)}\n"
                                f"Title: {updated_info.get('title', 'No title')}\n"
                                f"Current Price: {updated_info.get('price', 'N/A')} (sale pricing removed)\n"
                                f"Compare at Price: {updated_info.get('compare_at_price', 'N/A')}\n"
                                f"Available Quantity: {updated_info.get('available', 'N/A')}\n"
                                f"Vendor: {updated_info.get('vendor', 'N/A')}\n"
                                f"Type: {updated_info.get('product_type', 'N/A')}\n"
                                f"Tags: {updated_info.get('tags', '')}\n"
                                "Description:\n"
                                f"{updated_info.get('body_html', 'No description')}"
                            )
                        except Exception as e:
                            answer += (
                                "\n\nProduct taken off sale successfully, but unable to retrieve updated product info.\n"
                                f"SKU: {sku}\n"
                                f"Error: {str(e)}"
                            )
                    else:
                        error_message = off_sale_response.get("message", "Unknown error")
                        answer += f"\n\nFailed to take product off sale.\nError: {error_message}"

                elif tool_name == "disable_product_by_sku":
                    sku = args["sku"]
                    disable_response = disable_product_by_sku(sku)

                    # Print JSON for debugging
                    print("Disable Product Response JSON:", json.dumps(disable_response, indent=2))

                    if disable_response.get("status") == "success":
                        updated_fields = disable_response.get("updated_fields", {})
                        answer += (
                            "\n\nProduct successfully disabled!\n"
                            f"SKU: {updated_fields.get('sku', sku)}\n"
                            f"Title: {updated_fields.get('title', 'No title')}\n"
                            f"Price: {updated_fields.get('price', 'N/A')} (No longer available)\n"
                            f"Compare at Price: {updated_fields.get('compare_at_price', 'N/A')}\n"
                            f"Available Quantity: {updated_fields.get('available', 'N/A')}\n"
                            f"Vendor: {updated_fields.get('vendor', 'N/A')}\n"
                            f"Type: {updated_fields.get('product_type', 'N/A')}\n"
                            f"Tags: {updated_fields.get('tags', '')}\n"
                            "Description:\n"
                            f"{updated_fields.get('body_html', 'No description')}"
                        )
                    else:
                        error_message = disable_response.get("message", "Unknown error")
                        answer += f"\n\nFailed to disable product.\nError: {error_message}"

        return answer
    except Exception as e:
        print(e)
        return str(e)


@login_required
def home(request):
    if request.htmx and request.method == "POST":
        form = QuestionForm(request.POST, request.FILES)
        if form.is_valid():
            question = form.cleaned_data.get("question")
            uploaded_file = form.cleaned_data.get("file")
            apply_time = form.cleaned_data.get("apply_time")
            revert_time = form.cleaned_data.get("revert_time")
            csv_filename = None

            if uploaded_file:
                attachment_path = os.path.join(settings.MEDIA_ROOT, uploaded_file.name)
                with open(attachment_path, 'wb') as f:
                    for chunk in uploaded_file.chunks():
                        f.write(chunk)
                
                if uploaded_file.name.endswith('.csv') and ("update" in question.lower() or "create" in question.lower()):
                    csv_filename = attachment_path
            else:
                attachment_path = None

            answer = answer_question(
                question=question,
                debug=DEBUG, 
                uploaded_file=uploaded_file, 
                csv_filename=csv_filename,
                apply_time=apply_time,
                revert_time=revert_time,
                attachment_path=attachment_path
            )

            if "conversation_id" not in request.session:
                user = request.user
                conversation = Conversation.objects.create(title=question, user=user)
                request.session["conversation_id"] = conversation.id
            else:
                conversation_id = request.session["conversation_id"]
                conversation = get_object_or_404(Conversation, id=conversation_id)

            message = Message.objects.create(
                conversation=conversation,
                question=question,
                answer=answer,
                context=""
            )

            return render(request, "answer.html", {"answer": answer, "question": question})
    else:
        form = QuestionForm()
    return render(request, "home.html", {"form": form, "title": "Music Store Assistant"})
