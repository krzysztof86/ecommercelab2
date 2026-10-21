# -*- coding: utf-8 -*-
"""Zadanie 3: stan magazynu (StockRecord) i rezerwacje utworzone przez POST /inventory/reservations."""
import os
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1] / "mini-shop"
sys.path.insert(0, str(PROJECT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mini_shop.settings")
os.chdir(PROJECT)

import django  # noqa: E402

django.setup()

from oscar.core.loading import get_model  # noqa: E402

StockRecord = get_model("partner", "StockRecord")
print(f"{'product_id':>10}  {'produkt':<26} {'SKU':<10} {'na stanie':>9} {'zaalok.':>8} {'dostępne':>9}")
for s in StockRecord.objects.select_related("product").order_by("product_id"):
    allocated = s.num_allocated or 0
    print(f"{s.product_id:>10}  {s.product.get_title()[:26]:<26} {s.partner_sku:<10} {s.num_in_stock:>9} {allocated:>8} "
          f"{s.num_in_stock - allocated:>9}")
try:
    from inventory_api.models import Reservation

    reservations = list(Reservation.objects.order_by("pk"))
    print(f"\nRezerwacje w Inventory (inventory_api_reservation): {len(reservations)}")
    for r in reservations:
        print(f"  {r.public_id}  order_id={r.order_id}  product_id={r.product_id}  quantity={r.quantity}  status={r.status}")
except Exception:
    pass
