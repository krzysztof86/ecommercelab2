# -*- coding: utf-8 -*-
"""Zadanie 1 i 2: wspolna baza danych - tabele modulow i powiazania kluczami obcymi miedzy modulami."""
import os
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1] / "mini-shop"
sys.path.insert(0, str(PROJECT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mini_shop.settings")
os.chdir(PROJECT)

import django  # noqa: E402

django.setup()

import json  # noqa: E402
from collections import Counter  # noqa: E402

from django.apps import apps  # noqa: E402
from django.conf import settings  # noqa: E402
from django.db import connection  # noqa: E402

APPS = ["catalogue", "basket", "checkout", "order", "customer", "offer", "shipping", "payment", "partner"]
tables = set(connection.introspection.table_names())
owner = {m._meta.db_table: m._meta.app_label for m in apps.get_models()}
per_app = Counter(owner.get(t, "inne") for t in tables)

fks = []
for app in APPS:
    for model in apps.get_app_config(app).get_models():
        for f in model._meta.get_fields():
            if (f.many_to_one or f.one_to_one) and f.concrete and f.related_model is not None:
                target = f.related_model._meta.app_label
                if target != app and target in APPS:
                    fks.append({"from": f"{app}.{model.__name__}.{f.name}", "to": f"{target}.{f.related_model.__name__}",
                                "sql": f"{model._meta.db_table}.{f.column} -> {f.related_model._meta.db_table}"})

with connection.cursor() as c:
    c.execute("""SELECT o.number, l.title, l.quantity, s.partner_sku, s.num_in_stock, s.num_allocated
                 FROM order_line l
                 JOIN order_order o ON o.id = l.order_id
                 JOIN partner_stockrecord s ON s.id = l.stockrecord_id
                 ORDER BY o.number""")
    joined = c.fetchall()

db_name = Path(settings.DATABASES["default"]["NAME"]).name
if "--json" in sys.argv:
    print(json.dumps({"db": db_name, "tables": len(tables), "per_app": {a: per_app[a] for a in APPS},
                      "fks": fks, "join": joined}, ensure_ascii=False))
    sys.exit()

print(f"Baza danych {db_name}: {len(tables)} tabel w jednym pliku, wspólnych dla wszystkich modułów.")
print("Liczba tabel modułów Oscara w tej bazie:")
print("  " + ", ".join(f"{a}: {per_app[a]}" for a in APPS))
print(f"\nPowiązania kluczami obcymi między modułami ({len(fks)}):")
for x in fks:
    print(f"  {x['from']:<40} -> {x['to']:<24} ({x['sql']})")
print("\nJedno zapytanie SQL łączy tabele modułów order i partner (możliwe tylko przy wspólnej bazie):")
print("  SELECT ... FROM order_line JOIN order_order JOIN partner_stockrecord")
for r in joined:
    print(f"  zamówienie {r[0]}: {r[1]} x{r[2]} | SKU {r[3]}, na stanie {r[4]}, zaalokowano {r[5]}")
