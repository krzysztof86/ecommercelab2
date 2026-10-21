# -*- coding: utf-8 -*-
"""Pliki zapisywane do repozytorium LAB2 przez lab2_oscar_auto.py (analizy, przyklad API, symulacja platnosci)."""

BOOTSTRAP = '''import os
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1] / "mini-shop"
sys.path.insert(0, str(PROJECT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mini_shop.settings")
os.chdir(PROJECT)

import django  # noqa: E402

django.setup()
'''

ANALIZA_MODULOW = '''# -*- coding: utf-8 -*-
"""Zadanie 1: moduly Oscara - modele, rozmiar kodu i zaleznosci miedzy aplikacjami (analiza kodu oscar.apps)."""
''' + BOOTSTRAP + '''
import json  # noqa: E402
import re  # noqa: E402
from collections import Counter  # noqa: E402

import oscar  # noqa: E402
from django.apps import apps  # noqa: E402
from django.conf import settings  # noqa: E402

APPS = ["catalogue", "basket", "checkout", "order", "customer", "offer", "shipping", "payment", "partner"]
ROOT = Path(oscar.__file__).resolve().parent / "apps"
LABELS = {p.name for p in ROOT.iterdir() if p.is_dir() and not p.name.startswith("_")}
DEP_RE = re.compile(r"""get_(?:model|class|classes)\\(\\s*["']([a-z_]+)|from oscar\\.apps\\.([a-z_]+)""")


def analyse(app):
    files = [p for p in (ROOT / app).rglob("*.py") if "migrations" not in p.parts]
    deps = Counter()
    lines = 0
    for p in files:
        text = p.read_text(encoding="utf-8")
        lines += text.count("\\n")
        for m in DEP_RE.finditer(text):
            target = m.group(1) or m.group(2)
            if target in LABELS and target != app:
                deps[target] += 1
    models = [m.__name__ for m in apps.get_app_config(app).get_models()]
    return {"app": app, "models": models, "files": len(files), "lines": lines, "deps": deps.most_common()}


rows = [analyse(a) for a in APPS]
db_name = Path(settings.DATABASES["default"]["NAME"]).name
if "--json" in sys.argv:
    print(json.dumps({"rows": rows, "db": db_name}, ensure_ascii=False))
    sys.exit()

print("Aplikacje Oscara wykorzystywane w mini_shop (pakiet oscar.apps):\\n")
print(f"{'moduł':<10} {'modele':>6} {'pliki':>6} {'linie':>6}  zależy od (liczba odwołań get_model/get_class/import w kodzie)")
for r in rows:
    deps = ", ".join(f"{a}({n})" for a, n in r["deps"][:6])
    print(f"{r['app']:<10} {len(r['models']):>6} {r['files']:>6} {r['lines']:>6}  {deps}")
print("\\nModele (tabele) poszczególnych modułów:")
for r in rows:
    print(f"  {r['app']:<10} {', '.join(r['models']) or '(brak własnych modeli - steruje procesem, korzysta z innych modułów)'}")
print(f"\\nWszystkie moduły: jeden projekt Django, jeden proces Pythona (PID {os.getpid()}), jedna baza danych: {db_name}")
print("Komunikacja między modułami: wywołania klas i funkcji w tym samym procesie, a nie żądania sieciowe.")
'''

WSPOLNA_BAZA = '''# -*- coding: utf-8 -*-
"""Zadanie 1 i 2: wspolna baza danych - tabele modulow i powiazania kluczami obcymi miedzy modulami."""
''' + BOOTSTRAP + '''
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
print(f"\\nPowiązania kluczami obcymi między modułami ({len(fks)}):")
for x in fks:
    print(f"  {x['from']:<40} -> {x['to']:<24} ({x['sql']})")
print("\\nJedno zapytanie SQL łączy tabele modułów order i partner (możliwe tylko przy wspólnej bazie):")
print("  SELECT ... FROM order_line JOIN order_order JOIN partner_stockrecord")
for r in joined:
    print(f"  zamówienie {r[0]}: {r[1]} x{r[2]} | SKU {r[3]}, na stanie {r[4]}, zaalokowano {r[5]}")
'''

STAN_MAGAZYNU = '''# -*- coding: utf-8 -*-
"""Zadanie 3: stan magazynu (StockRecord) i rezerwacje utworzone przez POST /inventory/reservations."""
''' + BOOTSTRAP + '''
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
    print(f"\\nRezerwacje w Inventory (inventory_api_reservation): {len(reservations)}")
    for r in reservations:
        print(f"  {r.public_id}  order_id={r.order_id}  product_id={r.product_id}  quantity={r.quantity}  status={r.status}")
except Exception:
    pass
'''

INVENTORY_APPS = '''from django.apps import AppConfig


class InventoryApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "inventory_api"
    verbose_name = "Inventory API (LAB2 - kontrakt rezerwacji)"
'''

INVENTORY_MODELS = '''from django.db import models


class Reservation(models.Model):
    """Rezerwacja towaru - dane, ktorych wlascicielem jest (symulowany) Inventory Service.

    product_id i order_id to zwykle identyfikatory, a nie klucze obce: serwis magazynu nie siega
    do tabel katalogu ani zamowien, zna tylko identyfikatory przekazane w zadaniu API.
    """

    STATUS_RESERVED = "reserved"

    product_id = models.PositiveIntegerField()
    quantity = models.PositiveIntegerField()
    order_id = models.CharField(max_length=64)
    status = models.CharField(max_length=16, default=STATUS_RESERVED)
    created = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["order_id", "product_id"], name="uniq_reservation_order_product"),
        ]

    @property
    def public_id(self):
        return f"R-{self.pk:05d}"
'''

INVENTORY_VIEWS = '''import json
from datetime import timedelta

from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from oscar.core.loading import get_model

from .models import Reservation

StockRecord = get_model("partner", "StockRecord")
RESERVATION_TTL = timedelta(minutes=15)


def rejected(http_status, reason, **extra):
    return JsonResponse({"status": "rejected", "reason": reason, **extra}, status=http_status)


def reserved(reservation, http_status=201):
    return JsonResponse({
        "reservation_id": reservation.public_id,
        "status": "reserved",
        "product_id": reservation.product_id,
        "quantity": reservation.quantity,
        "order_id": reservation.order_id,
        "expires_at": reservation.expires_at.isoformat(timespec="seconds"),
    }, status=http_status)


@csrf_exempt
@require_POST
def create_reservation(request):
    """POST /inventory/reservations - rezerwacja produktu dla zamowienia."""
    try:
        data = json.loads(request.body)
        product_id = int(data["product_id"])
        quantity = int(data["quantity"])
        order_id = str(data["order_id"]).strip()
    except (ValueError, KeyError, TypeError):
        return rejected(400, "invalid_request")
    if quantity <= 0 or not order_id:
        return rejected(400, "invalid_request")

    with transaction.atomic():
        # Ponowienie tego samego zadania (retry) zwraca istniejaca rezerwacje - bez drugiej alokacji.
        existing = Reservation.objects.filter(order_id=order_id, product_id=product_id).first()
        if existing:
            return reserved(existing, http_status=200)

        stock = StockRecord.objects.select_for_update().filter(product_id=product_id).first()
        if stock is None:
            return rejected(404, "unknown_product")
        available = stock.net_stock_level
        if available < quantity:
            return rejected(409, "insufficient_stock", available=available)

        stock.allocate(quantity)
        reservation = Reservation.objects.create(
            product_id=product_id, quantity=quantity, order_id=order_id,
            expires_at=timezone.now() + RESERVATION_TTL,
        )
    return reserved(reservation)
'''

API_OK = '''{
  "product_id": 1,
  "quantity": 2,
  "order_id": "2026-00123"
}
'''

API_BRAK = '''{
  "product_id": 1,
  "quantity": 50,
  "order_id": "2026-00124"
}
'''

PAYMENT_DEMO = '''# -*- coding: utf-8 -*-
"""Zadanie 4: Payment Service nie odpowiada - dlaczego ponowienie platnosci wymaga klucza idempotencji.

Symulacja (tylko biblioteka standardowa):
  - lokalny "Payment Service" obciaza klienta, ale przy pierwszym zadaniu odpowiada po 2,5 s,
  - checkout czeka maksymalnie 1 s (timeout), wiec nie wie, czy platnosc sie udala,
  - checkout ponawia zadanie: bez klucza i z kluczem Idempotency-Key.
"""
import json
import socket
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LEDGER = []        # obciazenia faktycznie wykonane u klienta
BY_KEY = {}        # Idempotency-Key -> wynik pierwszego przetworzenia
SLOW = {"remaining": 0}
LOCK = threading.Lock()


class PaymentService(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        key = self.headers.get("Idempotency-Key")
        with LOCK:
            if key and key in BY_KEY:
                return self._send(200, {**BY_KEY[key], "replayed": True})
            charge = {"payment_id": f"P-{len(LEDGER) + 1:04d}", "order_id": body["order_id"],
                      "amount": body["amount"], "status": "captured"}
            LEDGER.append(charge)
            if key:
                BY_KEY[key] = charge
            slow = SLOW["remaining"] > 0
            if slow:
                SLOW["remaining"] -= 1
        if slow:  # pieniadze pobrane, ale odpowiedz przychodzi za pozno
            time.sleep(2.5)
        self._send(201, charge)

    def _send(self, status, payload):
        try:
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass  # klient juz sie rozlaczyl (timeout)

    def log_message(self, *args):
        pass


def pay(url, order_id, amount, key):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Idempotency-Key"] = key
    req = urllib.request.Request(url, data=json.dumps({"order_id": order_id, "amount": amount}).encode(),
                                 headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=1.0) as resp:
        return json.loads(resp.read())


def scenario(url, title, use_key):
    LEDGER.clear()
    BY_KEY.clear()
    SLOW["remaining"] = 1
    order_id, amount = "100003", "5998.00"
    key = f"payment-{order_id}-1" if use_key else None
    print(title)
    print(f"  Idempotency-Key: {key or '(brak)'}")
    for attempt in range(1, 4):
        try:
            result = pay(url, order_id, amount, key)
            print(f"  próba {attempt}: odpowiedź {result}")
            break
        except (TimeoutError, socket.timeout, urllib.error.URLError):
            print(f"  próba {attempt}: brak odpowiedzi w 1 s (timeout) -> status płatności NIEZNANY, ponawiam")
            time.sleep(0.3)
    time.sleep(2.6)  # czekamy, az "zawieszone" pierwsze zadanie sie zakonczy
    print(f"  obciążenia klienta w Payment Service: {len(LEDGER)} -> {', '.join(c['payment_id'] for c in LEDGER)}\\n")
    return len(LEDGER)


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), PaymentService)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/payments"
    print(f"Payment Service (symulacja): {url}\\n")
    bez = scenario(url, "Scenariusz A: ponowienie BEZ klucza idempotencji", use_key=False)
    z = scenario(url, "Scenariusz B: ponowienie Z kluczem Idempotency-Key (ten sam klucz w każdej próbie)", use_key=True)
    print(f"Wynik: bez klucza = {bez} obciążenia (podwójna płatność), z kluczem = {z} obciążenie.")
    server.shutdown()


if __name__ == "__main__":
    main()
'''

GITIGNORE = '''.venv/
__pycache__/
*.pyc
mini-shop/staticfiles/
mini-shop/whoosh_index/
state.json
server*.log
.lab2_auto
dane_testowe.txt
'''

README = '''# LAB2 – Django Oscar jako architektura e-commerce

Repozytorium do laboratorium 2. Punktem wyjścia jest projekt `mini-shop` z laboratorium 1
(Django Oscar, SQLite, wyszukiwarka Whoosh).

## Struktura

```
django-oscar-lab2/
  .venv/                    środowisko wirtualne (poza repozytorium)
  mini-shop/                projekt Django Oscar z LAB1
    inventory_api/          LAB2, zad. 3 – przykład kontraktu POST /inventory/reservations
  analiza/                  LAB2, zad. 1–2 – analiza modułów Oscara i wspólnej bazy danych
  api_przyklady/            LAB2, zad. 3 – przykładowe żądania JSON
  symulacje/                LAB2, zad. 4 – awaria Payment Service i ponowienie z kluczem idempotencji
  docs/                     LAB2, zad. 5 – diagram architektury sklepu
  zrzuty/                   zrzuty ekranu do sprawozdania
```

## Uruchomienie (PowerShell)

```
.venv\\Scripts\\Activate.ps1
cd mini-shop
python manage.py runserver
python ..\\analiza\\analiza_modulow.py
python ..\\analiza\\wspolna_baza.py
python ..\\symulacje\\payment_retry_demo.py
```

Rezerwacja (przy działającym serwerze):

```
curl.exe -s -X POST http://127.0.0.1:8000/inventory/reservations -H "Content-Type: application/json" --data-binary "@..\\api_przyklady\\rezerwacja_ok.json"
```

`inventory_api` to symulacja kontraktu w monolicie – w laboratorium nie budujemy prawdziwych mikroserwisów.
'''
