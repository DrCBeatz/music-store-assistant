# shopify_chat_cli.py

from openai import OpenAI
from decouple import config
import requests
import shopify
import json
import csv
import os

OPENAI_API_KEY = config("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

ACCESS_TOKEN = config('SHOPIFY_ACCESS_TOKEN')
STORE_NAME = config('SHOPIFY_STORE_URL')
VERSION = "2024-10"

session = shopify.Session(STORE_NAME, VERSION, ACCESS_TOKEN)
shopify.ShopifyResource.activate_session(session)
shop = shopify.Shop.current

def find_product_by_sku(sku):
    products = shopify.Product.find(limit=250)
    while True:
        for product in products:
            for variant in product.variants:
                if variant.sku == sku:
                    return product, variant
        if hasattr(products, 'has_next_page') and products.has_next_page():
            products = products.next_page()
        else:
            break
    return None, None

def get_product_info_by_sku(sku):
    product, variant = find_product_by_sku(sku)
    if not product or not variant:
        raise Exception(f"Could not find product with SKU '{sku}'")

    inventory_item_id = variant.inventory_item_id
    inventory_item = shopify.InventoryItem.find(inventory_item_id)
    cost = inventory_item.cost if hasattr(inventory_item, 'cost') else None

    inventory_levels = shopify.InventoryLevel.find(inventory_item_ids=inventory_item_id)
    available = None
    if inventory_levels:
        first_level = inventory_levels[0]
        available = first_level.available

    result = {
        "title": product.title,
        "product_type": product.product_type,
        "vendor": product.vendor,
        "tags": product.tags,
        "sku": variant.sku,
        "price": variant.price,
        "compare_at_price": variant.compare_at_price,
        "cost": cost,
        "available": available,
        "body_html": product.body_html
    }
    return result

def update_product_by_sku(sku, update_fields):
    product, variant = find_product_by_sku(sku)
    if not product or not variant:
        return {"status": "error", "message": f"Could not find product with SKU '{sku}'"}

    # Product-level fields
    if "title" in update_fields:
        product.title = update_fields["title"]
    if "product_type" in update_fields:
        product.product_type = update_fields["product_type"]
    if "vendor" in update_fields:
        product.vendor = update_fields["vendor"]
    if "tags" in update_fields:
        product.tags = update_fields["tags"]
    if "body_html" in update_fields:
        product.body_html = update_fields["body_html"]

    # Variant-level fields
    if "price" in update_fields:
        variant.price = str(update_fields["price"])
    if "compare_at_price" in update_fields:
        variant.compare_at_price = str(update_fields["compare_at_price"])

    # Save changes so far
    if not product.save():
        errors = product.errors.full_messages() if product.errors else ["Unknown error"]
        return {"status": "error", "message": f"Failed to update product. Errors: {errors}"}

    # Now handle inventory-related updates
    inventory_item_id = variant.inventory_item_id
    inventory_item = shopify.InventoryItem.find(inventory_item_id)

    # Update cost if provided
    if "cost" in update_fields:
        inventory_item.cost = str(update_fields["cost"])
        if not inventory_item.save():
            errors = inventory_item.errors.full_messages() if inventory_item.errors else ["Unknown error"]
            return {"status": "error", "message": f"Failed to update inventory item cost. Errors: {errors}"}

    # Update available quantity if provided
    if "available" in update_fields:
        # Ensure inventory is managed by Shopify at the variant level
        if variant.inventory_management != "shopify":
            variant.inventory_management = "shopify"
            # Save product changes again after modifying the variant
            if not product.save():
                errors = product.errors.full_messages() if product.errors else ["Unknown error"]
                return {"status": "error", "message": f"Failed to enable Shopify inventory management. Errors: {errors}"}

        # Ensure the inventory item is tracked
        if not getattr(inventory_item, 'tracked', False):
            inventory_item.tracked = True
            if not inventory_item.save():
                errors = inventory_item.errors.full_messages() if inventory_item.errors else ["Unknown error"]
                return {"status": "error", "message": f"Failed to enable tracking on inventory item. Errors: {errors}"}

        # Now that management and tracking are enabled, set the available quantity
        inventory_levels = shopify.InventoryLevel.find(inventory_item_ids=inventory_item_id)
        if inventory_levels:
            first_level = inventory_levels[0]
            location_id = first_level.location_id
            new_available = int(update_fields["available"])
            shopify.InventoryLevel.set(inventory_item_id=inventory_item_id,
                                       location_id=location_id,
                                       available=new_available)

    return {
        "status": "success",
        "message": "The product was successfully updated.",
        "updated_fields": get_product_info_by_sku(sku)
    }

def create_product_with_sku(sku, **fields):
    if not sku:
        return {"status": "error", "message": "SKU is required"}

    title = fields.get("title", "New Product")
    product_type = fields.get("product_type")
    vendor = fields.get("vendor")
    tags = fields.get("tags")
    body_html = fields.get("body_html")
    price = str(fields.get("price", "0.00"))
    compare_at_price = fields.get("compare_at_price")
    cost = fields.get("cost")
    available = fields.get("available")

    new_product = shopify.Product()
    new_product.title = title
    if product_type:
        new_product.product_type = product_type
    if vendor:
        new_product.vendor = vendor
    if tags:
        new_product.tags = tags
    if body_html:
        new_product.body_html = body_html

    variant = shopify.Variant()
    variant.sku = sku
    variant.price = price
    # Enable Shopify inventory management on the variant
    variant.inventory_management = "shopify"
    if compare_at_price:
        variant.compare_at_price = str(compare_at_price)

    new_product.variants = [variant]

    # Save the product
    if not new_product.save():
        errors = new_product.errors.full_messages() if new_product.errors else ["Unknown error"]
        return {"status": "error", "message": f"Failed to create product. Errors: {errors}"}

    # Product and variant created successfully. Retrieve them
    created_product, created_variant = find_product_by_sku(sku)
    if not created_product or not created_variant:
        return {"status": "error", "message": "Product was created but could not be retrieved by SKU."}

    inventory_item_id = created_variant.inventory_item_id
    inventory_item = shopify.InventoryItem.find(inventory_item_id)

    # Enable inventory tracking on the inventory item
    inventory_item.tracked = True
    if not inventory_item.save():
        errors = inventory_item.errors.full_messages() if inventory_item.errors else ["Unknown error"]
        return {"status": "error", "message": f"Product created, but failed to update inventory tracking. Errors: {errors}"}

    # Update cost if provided
    if cost is not None:
        inventory_item.cost = str(cost)
        if not inventory_item.save():
            errors = inventory_item.errors.full_messages() if inventory_item.errors else ["Unknown error"]
            return {"status": "error", "message": f"Product created, but failed to update cost. Errors: {errors}"}

    # Update available quantity if provided
    if available is not None:
        # Now that tracking is enabled, we can set the available level
        inventory_levels = shopify.InventoryLevel.find(inventory_item_ids=inventory_item_id)
        if inventory_levels:
            first_level = inventory_levels[0]
            location_id = first_level.location_id
            new_available = int(available)
            shopify.InventoryLevel.set(
                inventory_item_id=inventory_item_id,
                location_id=location_id,
                available=new_available
            )

    product_info = get_product_info_by_sku(sku)
    return {
        "status": "success",
        "message": "The product was successfully created.",
        "product_info": product_info
    }

def put_product_on_sale(sku, sale_price, regular_price, tags_to_add=["on-sale"]):
    product, variant = find_product_by_sku(sku)
    if not product or not variant:
        raise Exception(f"Could not find a product variant with SKU '{sku}'")

    variant.price = str(sale_price)
    variant.compare_at_price = str(regular_price)

    if not product.save():
        errors = product.errors.full_messages() if product.errors else ["Unknown error"]
        raise Exception(f"Failed to update product pricing. Errors: {errors}")

    current_tags = product.tags.split(",") if product.tags else []
    current_tags = [t.strip() for t in current_tags if t.strip()]

    for tag in tags_to_add:
        if tag not in current_tags:
            current_tags.append(tag)
    product.tags = ", ".join(current_tags)

    if not product.save():
        errors = product.errors.full_messages() if product.errors else ["Unknown error"]
        raise Exception(f"Failed to update product tags. Errors: {errors}")

    return {"status": "success", "message": f"Product with SKU '{sku}' put on sale."}

def take_product_off_sale(sku, tags_to_remove=["on-sale"]):
    product, variant = find_product_by_sku(sku)
    if not product or not variant:
        raise Exception(f"Could not find a product variant with SKU '{sku}'")

    # Move compare_at_price back to price and clear compare_at_price
    if variant.compare_at_price:
        variant.price = variant.compare_at_price
        variant.compare_at_price = None

    if not product.save():
        errors = product.errors.full_messages() if product.errors else ["Unknown error"]
        raise Exception(f"Failed to update product pricing. Errors: {errors}")

    current_tags = product.tags.split(",") if product.tags else []
    current_tags = [t.strip() for t in current_tags if t.strip()]
    updated_tags = [tag for tag in current_tags if tag not in tags_to_remove]
    product.tags = ", ".join(updated_tags)

    if not product.save():
        errors = product.errors.full_messages() if product.errors else ["Unknown error"]
        raise Exception(f"Failed to update product tags. Errors: {errors}")

    return {"status": "success", "message": f"Product with SKU '{sku}' taken off sale."}

def disable_product_by_sku(sku):
    product, variant = find_product_by_sku(sku)
    if not product or not variant:
        return {"status": "error", "message": f"Could not find product with SKU '{sku}'"}

    old_title = product.title or ""
    old_body_html = product.body_html or ""

    # Update fields to match the disable logic
    product.title = f"Unavailable - {old_title}"
    product.product_type = "Unavailable"
    product.tags = ""
    product.body_html = f"<p><strong>Unfortunately this item is no longer available for purchase</strong></p> {old_body_html}"

    # Update variant inventory policy
    variant.inventory_policy = "deny"

    if not product.save():
        errors = product.errors.full_messages() if product.errors else ["Unknown error"]
        return {"status": "error", "message": f"Failed to disable product. Errors: {errors}"}

    return {
        "status": "success",
        "message": "The product was successfully disabled.",
        "updated_fields": get_product_info_by_sku(sku)
    }

def send_email(recipient, subject, body):
    mailgun_domain = config("MAILGUN_DOMAIN")
    mailgun_api_key = config("MAILGUN_API_KEY")
    from_email = config("FROM_EMAIL")

    try:
        print(f"Sending email to: {recipient}, Subject: {subject}, Body: {body}")
        response = requests.post(
            f"https://api.mailgun.net/v3/{mailgun_domain}/messages",
            auth=("api", mailgun_api_key),
            data={"from": from_email, "to": recipient, "subject": subject, "text": body},
        )
        response.raise_for_status()
        return {"status": "success", "details": response.json()}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "details": str(e)}

def create_products_from_csv(filename):
    if not os.path.exists(filename):
        return {"status": "error", "message": f"File '{filename}' not found."}

    results = []
    with open(filename, mode='r', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)

        if 'sku' not in reader.fieldnames:
            return {"status": "error", "message": "CSV must contain a 'sku' column."}

        for row in reader:
            sku = row.get('sku', '').strip()
            if not sku:
                results.append({"sku": None, "response": {"status": "error", "message": "No SKU provided"}})
                continue

            response = create_product_with_sku(
                sku=sku,
                title=row.get('title'),
                product_type=row.get('product_type'),
                vendor=row.get('vendor'),
                tags=row.get('tags'),
                body_html=row.get('body_html'),
                price=row.get('price'),
                compare_at_price=row.get('compare_at_price'),
                cost=row.get('cost'),
                available=row.get('available')
            )
            results.append({"sku": sku, "response": response})

    # Transform 'results' into a user-friendly summary
    created_products = []
    error_messages = []

    for r in results:
        resp = r["response"]
        if resp.get("status") == "success":
            # resp["product_info"] holds details about the created product
            product_info = resp.get("product_info", {})
            created_products.append({
                "sku": product_info.get("sku", r["sku"]),
                "title": product_info.get("title", "Unknown Title")
            })
        else:
            error_messages.append(f"SKU {r['sku']}: {resp.get('message', 'Unknown error')}")

    if created_products:
        return {
            "status": "success",
            "message": "Products processed from CSV.",
            "created_products": created_products,
            "errors": error_messages
        }
    else:
        return {
            "status": "error",
            "message": "No products were successfully created.",
            "errors": error_messages
        }


def update_products_from_csv(filename):
    if not os.path.exists(filename):
        return {"status": "error", "message": f"File '{filename}' not found."}

    results = []
    with open(filename, mode='r', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)

        if 'sku' not in reader.fieldnames:
            return {"status": "error", "message": "CSV must contain a 'sku' column."}

        for row in reader:
            sku = row.get('sku', '').strip()
            if not sku:
                results.append({"sku": None, "response": {"status": "error", "message": "No SKU provided"}})
                continue

            update_fields = {}
            for field in ["title", "product_type", "vendor", "tags", "body_html", "price", "compare_at_price", "cost"]:
                if row.get(field):
                    update_fields[field] = row.get(field)

            if row.get('available'):
                try:
                    update_fields['available'] = int(row.get('available'))
                except ValueError:
                    pass

            response = update_product_by_sku(sku, update_fields)
            results.append({"sku": sku, "response": response})

    # Transform 'results' into a user-friendly summary
    updated_products = []
    error_messages = []

    for r in results:
        resp = r["response"]
        if resp.get("status") == "success":
            updated_fields = resp.get("updated_fields", {})
            updated_products.append({
                "sku": updated_fields.get("sku", r["sku"]),
                "title": updated_fields.get("title", "Unknown Title")
            })
        else:
            error_messages.append(f"SKU {r['sku']}: {resp.get('message', 'Unknown error')}")

    if updated_products:
        return {
            "status": "success",
            "message": "Products updated from CSV.",
            "updated_products": updated_products,
            "errors": error_messages
        }
    else:
        return {
            "status": "error",
            "message": "No products were successfully updated.",
            "errors": error_messages
        }

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
            "description": "Create multiple products from a CSV file. The CSV must have a 'sku' column. Other columns are optional.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "The name of the CSV file in the same directory."}
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_products_from_csv",
            "description": "Update multiple existing products from a CSV file using their SKU. The CSV must have a 'sku' column. Other columns are optional.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "The name of the CSV file in the same directory."}
                },
                "required": ["filename"]
            }
        }
    },
]

if __name__ == "__main__":
    while True:
        user_input = input(":")
        messages = [
            {"role": "system", "content": "You are a helpful assistant for the music store All You Need Music. You can send emails, retrieve product information by SKU, create products, update products, and process CSV files."},
            {"role": "user", "content": user_input},
        ]

        completion = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=messages,
            tools=tools,
        )

        message = completion.choices[0].message

        if message.tool_calls:
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                args = eval(tool_call.function.arguments)

                if tool_name == "send_email":
                    response = send_email(args["recipient"], args["subject"], args["body"])
                    messages.append({"role": "function", "name": tool_name, "content": json.dumps(response)})

                elif tool_name == "get_product_info_by_sku":
                    response = get_product_info_by_sku(args["sku"])
                    messages.append({"role": "function", "name": tool_name, "content": json.dumps(response)})
                    messages.append({"role": "system", "content": "Please summarize the product information requested above for the user in a helpful manner."})
                    followup_completion = client.chat.completions.create(model='gpt-4o-mini', messages=messages, tools=tools)
                    final_message = followup_completion.choices[0].message
                    print(final_message.content)

                elif tool_name == "update_product_by_sku":
                    update_fields = {k: v for k, v in args.items() if k != "sku"}
                    response = update_product_by_sku(args["sku"], update_fields)
                    messages.append({"role": "function", "name": tool_name, "content": json.dumps(response)})
                    messages.append({"role": "system", "content": "The update has been processed. Provide a confirmation message to the user."})
                    followup_completion = client.chat.completions.create(model='gpt-4o-mini', messages=messages, tools=tools)
                    final_message = followup_completion.choices[0].message
                    print(final_message.content)

                elif tool_name == "create_product_with_sku":
                    create_fields = {k: v for k, v in args.items() if k != "sku"}
                    response = create_product_with_sku(args["sku"], **create_fields)
                    messages.append({"role": "function", "name": tool_name, "content": json.dumps(response)})
                    messages.append({"role": "system", "content": "The product has been created. Provide a confirmation message to the user."})
                    followup_completion = client.chat.completions.create(model='gpt-4o-mini', messages=messages, tools=tools)
                    final_message = followup_completion.choices[0].message
                    print(final_message.content)

                elif tool_name == "put_product_on_sale":
                    response = put_product_on_sale(args["sku"], args["sale_price"], args["regular_price"], args.get("tags_to_add", ["on-sale"]))
                    print(f"Tool response: {response}")

                elif tool_name == "take_product_off_sale":
                    response = take_product_off_sale(args["sku"], args.get("tags_to_remove", ["on-sale"]))
                    print(f"Tool response: {response}")

                elif tool_name == "disable_product_by_sku":
                    response = disable_product_by_sku(args["sku"])
                    messages.append({"role": "function", "name": tool_name, "content": json.dumps(response)})
                    messages.append({"role": "system", "content": "The product has been disabled. Provide a confirmation message to the user."})
                    followup_completion = client.chat.completions.create(model='gpt-4o-mini', messages=messages, tools=tools)
                    final_message = followup_completion.choices[0].message
                    print(final_message.content)

                elif tool_name == "create_products_from_csv":
                    response = create_products_from_csv(args["filename"])
                    messages.append({"role": "function", "name": tool_name, "content": json.dumps(response)})
                    messages.append({"role": "system", "content": "The products have been processed from the CSV. Provide a summary to the user."})
                    followup_completion = client.chat.completions.create(model='gpt-4o-mini', messages=messages, tools=tools)
                    final_message = followup_completion.choices[0].message
                    print(final_message.content)

                elif tool_name == "update_products_from_csv":
                    response = update_products_from_csv(args["filename"])
                    messages.append({"role": "function", "name": tool_name, "content": json.dumps(response)})
                    messages.append({"role": "system", "content": "The products have been updated from the CSV. Provide a summary to the user."})
                    followup_completion = client.chat.completions.create(model='gpt-4o-mini', messages=messages, tools=tools)
                    final_message = followup_completion.choices[0].message
                    print(final_message.content)

        else:
            print(message.content)
