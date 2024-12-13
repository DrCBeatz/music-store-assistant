# assistant/tasks.py
from celery import shared_task
from .shopify_chat_cli import update_products_from_csv, get_product_info_by_sku
from .models import ProductSnapshot
import os, uuid, csv

def get_skus_from_csv(csv_path):
    skus = []
    with open(csv_path, mode='r', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)
        if 'sku' not in reader.fieldnames:
            return skus
        for row in reader:
            sku = row.get('sku', '').strip()
            if sku:
                skus.append(sku)
    return skus

@shared_task
def apply_csv_updates(csv_path):
    batch_id = str(uuid.uuid4())  # Unique ID for this batch of updates

    # Extract SKUs from CSV to know which products we will update
    skus = get_skus_from_csv(csv_path)

    # Store snapshots before applying updates
    for sku in skus:
        try:
            product_info = get_product_info_by_sku(sku)
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

    # Now apply updates
    response = update_products_from_csv(csv_path)
    print("Applied updates:", response, "Batch ID:", batch_id)

    # Optionally return the batch_id so you can revert later by referencing it
    return {"batch_id": batch_id}

@shared_task
def revert_csv_updates(batch_id):
    # Find all snapshots for this batch_id and revert them
    snapshots = ProductSnapshot.objects.filter(batch_id=batch_id, reverted=False)
    from .shopify_chat_cli import update_product_by_sku

    for snap in snapshots:
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
        # Remove fields that are None to avoid unnecessary updates
        update_fields = {k: v for k, v in update_fields.items() if v is not None}
        response = update_product_by_sku(snap.sku, update_fields)
        print(f"Reverted {snap.sku}: {response}")

    snapshots.update(reverted=True)
    print(f"Reverted batch {batch_id}")
