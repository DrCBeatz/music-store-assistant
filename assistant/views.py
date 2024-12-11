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
)
from environs import Env
import requests
import json
import csv
from io import TextIOWrapper
import tempfile
from openai import OpenAI

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
            "description": "Send an email to a recipient",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["recipient", "subject", "body"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_info_by_sku",
            "description": "Retrieve product information by SKU",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string", "description": "The SKU of the product variant"}
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

def send_email(recipient, subject, body, attachment=None):
    mailgun_domain = env("MAILGUN_DOMAIN")
    mailgun_api_key = env("MAILGUN_API_KEY")
    from_email = env("FROM_EMAIL")

    data = {
        "from": from_email,
        "to": recipient,
        "subject": subject,
        "text": body
    }

    files = []
    if attachment:
        attachment.seek(0)  # Ensure we are at the start of the file
        file_content = attachment.read()  # Read the file content
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
):
    """
    Return the assistant's entire response, including model output and tool call results.
    Handles tool calls and can attach the uploaded file if requested.
    """
    context = ""
    if debug:
        print("Context:\n" + context)

    try:
        prompt = f"""{PROMPT}```Context: {context}```\n\n---\n\n``Question: {question}```\n Answer:"""

        response = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant. You can send emails and interact with Shopify products using the provided functions.",
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
                    # If we have an uploaded file, attach it
                    email_response = send_email(
                        args["recipient"],
                        args["subject"],
                        args["body"],
                        attachment=uploaded_file if uploaded_file else None
                    )
                    answer += f"\n\nEmail Response:\n{json.dumps(email_response, indent=2)}"

                elif tool_name == "get_product_info_by_sku":
                    product_info = get_product_info_by_sku(args["sku"])
                    answer += f"\n\nProduct Info:\n{json.dumps(product_info, indent=2)}"

                elif tool_name == "update_product_by_sku":
                    update_fields = {k: v for k, v in args.items() if k != "sku"}
                    update_response = update_product_by_sku(args["sku"], update_fields)
                    answer += f"\n\nUpdate Product Response:\n{json.dumps(update_response, indent=2)}"

                elif tool_name == "create_product_with_sku":
                    create_fields = {k: v for k, v in args.items() if k != "sku"}
                    create_response = create_product_with_sku(args["sku"], **create_fields)
                    answer += f"\n\nCreate Product Response:\n{json.dumps(create_response, indent=2)}"

                elif tool_name == "create_products_from_csv":
                    if csv_filename:
                        # Always use our local csv_filename
                        create_response = create_products_from_csv(csv_filename)
                        answer += f"\n\nCreate Products From CSV Response:\n{json.dumps(create_response, indent=2)}"
                    else:
                        answer += "\n\nError: No CSV file provided."
                
                elif tool_name == "update_products_from_csv":
                    if csv_filename:
                        # Always use our local csv_filename
                        update_response = update_products_from_csv(csv_filename)
                        answer += f"\n\nUpdate Products From CSV Response:\n{json.dumps(update_response, indent=2)}"
                    else:
                        answer += "\n\nError: No CSV file provided."


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
            csv_filename = None

            # If a file was uploaded and it's a CSV, save it temporarily
            if uploaded_file and uploaded_file.name.endswith('.csv'):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp_file:
                    for chunk in uploaded_file.chunks():
                        tmp_file.write(chunk)
                csv_filename = tmp_file.name

            # Generate the answer from the assistant, passing uploaded file and csv_filename
            answer = answer_question(question=question, debug=DEBUG, uploaded_file=uploaded_file, csv_filename=csv_filename)

            # Handle conversation logic
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
