# assistant/tasks.py
import os, csv, time, random
from celery import shared_task
from django.db import transaction
from django.conf import settings

from .models import ProductSnapshot
from .shopify_chat_cli import update_product_by_sku, get_product_info_by_sku
from .views import send_email


def get_skus_and_fields(csv_path):
    """
    Return a list of (sku, fields_dict) from the CSV,
    where fields_dict is all relevant fields for update.
    e.g. [("SKU123", {"price": "19.99", "available": 5}), ...]
    """
    items = []
    with open(csv_path, mode='r', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)
        if 'sku' not in reader.fieldnames:
            return items

        for row in reader:
            sku = row.get('sku', '').strip()
            if not sku:
                continue
            # Gather other fields if they exist in the CSV
            # e.g. price, compare_at_price, etc.
            fields_dict = {}
            if 'price' in reader.fieldnames and row['price']:
                fields_dict['price'] = row['price'].strip()
            if 'compare_at_price' in reader.fieldnames and row['compare_at_price']:
                fields_dict['compare_at_price'] = row['compare_at_price'].strip()
            if 'available' in reader.fieldnames and row['available']:
                # Convert to int
                fields_dict['available'] = int(row['available'].strip())
            if 'title' in reader.fieldnames and row['title']:
                fields_dict['title'] = row['title'].strip()
            if 'vendor' in reader.fieldnames and row['vendor']:
                fields_dict['vendor'] = row['vendor'].strip()
            if 'product_type' in reader.fieldnames and row['product_type']:
                fields_dict['product_type'] = row['product_type'].strip()
            if 'tags' in reader.fieldnames:
                raw_tags = row.get('tags', '').strip()  # row['tags'] might be "", "nan", or something
                if raw_tags.lower() not in ('nan', ''):
                    fields_dict['tags'] = raw_tags
            if 'body_html' in reader.fieldnames and row['body_html']:
                fields_dict['body_html'] = row['body_html'].strip()
            if 'cost' in reader.fieldnames and row['cost']:
                fields_dict['cost'] = row['cost'].strip()

            items.append((sku, fields_dict))
    return items


class ShopifyRateLimitError(Exception):
    """Custom exception to handle 429 from Shopify.""" 
    def __init__(self, retry_after=2.0, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.retry_after = retry_after


def safe_shopify_call(func, *args, **kwargs):
    """
    Wrapper that calls a Shopify function, catching 429 errors,
    sleeping for retry-after, and retrying up to a few times.
    """
    MAX_RETRIES = 6
    attempt = 0

    while attempt < MAX_RETRIES:
        try:
            return func(*args, **kwargs)
        except ShopifyRateLimitError as e:
            # Sleep for the recommended time + small random offset
            delay = e.retry_after + random.uniform(0.2, 0.5)
            print(f"[RateLimit] 429 received. Sleeping {delay:.2f}s then retrying...")
            time.sleep(delay)
            attempt += 1
        except Exception as ex:
            # If some other error, decide how to handle it; for demonstration
            # we just re-raise. You might do your own logging, etc.
            print(f"[Error] {ex}")
            raise

    raise Exception("Too many 429s or errors, giving up after retries.")


@shared_task
def apply_csv_updates(csv_path, batch_id=None):
    """
    For each SKU in the CSV:
      1. GET product info, store snapshot.
      2. Sleep ~0.5–0.7s.
      3. Perform the product update from CSV fields.
      4. Sleep ~0.5–0.7s.
    """
    items = get_skus_and_fields(csv_path)

    for sku, fields_dict in items:
        # 1) Get and snapshot
        try:
            product_info = safe_shopify_call(get_product_info_by_sku, sku)
            ProductSnapshot.objects.create(
                batch_id=batch_id,
                sku=sku,
                title=product_info.get('title'),
                product_type=product_info.get('product_type'),
                vendor=product_info.get('vendor'),
                tags=product_info.get('tags'),
                body_html=product_info.get('body_html'),
                price=product_info.get('price'),
                compare_at_price=product_info.get('compare_at_price'),
                cost=product_info.get('cost'),
                available=product_info.get('available')
            )
        except Exception as e:
            print(f"Failed to store snapshot for SKU {sku}: {e}")
            # Decide if you want to continue or break. We'll continue.

        # 2) Sleep 0.5–0.7s
        time.sleep(random.uniform(0.5, 0.7))

        # 3) Update product
        try:
            if fields_dict:
                update_response = safe_shopify_call(update_product_by_sku, sku, fields_dict)
                print(f"Updated {sku}: {update_response}")
        except Exception as e:
            print(f"Failed to update {sku}: {e}")
            # continue or break, your choice. We'll continue.

        # 4) Sleep again
        time.sleep(random.uniform(0.5, 0.7))

    print("Done applying CSV updates, batch_id =", batch_id)
    return {"batch_id": batch_id}


@shared_task
def revert_csv_updates(batch_id):
    """
    Loop over all snapshots for batch_id. For each:
      - Put original fields back via safe_shopify_call
      - Mark snapshot as reverted
    """
    snapshots = ProductSnapshot.objects.filter(batch_id=batch_id, reverted=False)

    for snap in snapshots:
        try:
            # Build update fields from snapshot
            update_fields = {
                "title": snap.title,
                "product_type": snap.product_type,
                "vendor": snap.vendor,
                "tags": snap.tags,
                "body_html": snap.body_html,
                "price": snap.price,
                "compare_at_price": snap.compare_at_price,
                "cost": snap.cost,
                "available": snap.available
            }
            update_fields = {k: v for k, v in update_fields.items() if v is not None}

            safe_shopify_call(update_product_by_sku, snap.sku, update_fields)
            print(f"Reverted {snap.sku}")
        except Exception as e:
            print(f"Failed to revert {snap.sku}: {e}")
            # continue or break, up to you

        # Mark snapshot as reverted
        snap.reverted = True
        snap.save()

        # Sleep a bit between each revert call
        time.sleep(random.uniform(0.5, 0.7))

    print(f"Reverted batch {batch_id}")


@shared_task
def send_scheduled_email(recipients, subject, body, attachment_path=None):
    # (unchanged)
    import os
    attachment = None
    if attachment_path and os.path.exists(attachment_path):
        attachment = open(attachment_path, 'rb')
    try:
        response = send_email(recipients, subject, body, attachment=attachment)
        print(f"Scheduled email response: {response}")
        return response
    finally:
        if attachment:
            attachment.close()
