from django.contrib import admin
from django.urls import include, path
from django.apps import apps

from inventory_api.views import create_reservation

urlpatterns = [
    path('admin/', admin.site.urls),
    path('inventory/reservations', create_reservation, name='inventory-reservations'),
    path('', include(apps.get_app_config('oscar').urls[0])),
]
