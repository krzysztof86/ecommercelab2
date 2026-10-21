from django.db import models


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
