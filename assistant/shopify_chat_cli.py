# shopify_chat_cli.py

from openai import OpenAI
from decouple import config
import requests
import shopify
import json

OPENAI_API_KEY = config("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

ACCESS_TOKEN = config('SHOPIFY_ACCESS_TOKEN')
STORE_NAME = "aynm-test-store.myshopify.com"
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
    }
]

if __name__ == "__main__":
    while True:
        user_input = input(":")
        messages = [
            {"role": "system", "content": "You are a helpful assistant. You can send emails, retrieve product information by SKU, and update product fields by SKU. Use 'send_email', 'get_product_info_by_sku', or 'update_product_by_sku' functions as needed."},
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
                    # Add the tool's return to the messages
                    messages.append({"role": "function", "name": tool_name, "content": json.dumps(response)})
                    # Prompt the model to provide a summary to the user
                    messages.append({"role": "system", "content": "Please summarize the product information requested above for the user in a helpful manner."})

                    followup_completion = client.chat.completions.create(
                        model='gpt-4o-mini',
                        messages=messages,
                        tools=tools,
                    )
                    final_message = followup_completion.choices[0].message
                    print(final_message.content)

                elif tool_name == "update_product_by_sku":
                    update_fields = {k: v for k, v in args.items() if k != "sku"}
                    response = update_product_by_sku(args["sku"], update_fields)
                    messages.append({"role": "function", "name": tool_name, "content": json.dumps(response)})
                    # Add a system or assistant message to prompt the model:
                    messages.append({"role": "system", "content": "The update has been processed. Provide a confirmation message to the user."})

                    followup_completion = client.chat.completions.create(
                        model='gpt-4o-mini',
                        messages=messages,
                        tools=tools,
                    )
                    final_message = followup_completion.choices[0].message
                    print(final_message.content)
                
                elif tool_name == "create_product_with_sku":
                    # Extract fields from args, excluding sku
                    create_fields = {k: v for k, v in args.items() if k != "sku"}
                    response = create_product_with_sku(args["sku"], **create_fields)
                    messages.append({"role": "function", "name": tool_name, "content": json.dumps(response)})
                    # After creation, prompt the model to provide a confirmation
                    messages.append({"role": "system", "content": "The product has been created. Provide a confirmation message to the user."})

                    followup_completion = client.chat.completions.create(
                        model='gpt-4o-mini',
                        messages=messages,
                        tools=tools,
                    )
                    final_message = followup_completion.choices[0].message
                    print(final_message.content)
        
        else:
            print(message.content)
