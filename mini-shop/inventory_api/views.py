import json
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
