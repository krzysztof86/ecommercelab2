# LAB2 – Django Oscar jako architektura e-commerce

Repozytorium do laboratorium 2. Punktem wyjścia jest projekt `mini-shop` z laboratorium 1
(Django Oscar, SQLite, wyszukiwarka Whoosh).

## Struktura

```
lab2/
  Sprawozdanie_LAB2_Django_Oscar.docx   gotowe sprawozdanie
  requirements.txt          zależności projektu
  .venv/                    środowisko wirtualne (poza repozytorium)
  mini-shop/                projekt Django Oscar z LAB1
    inventory_api/          LAB2, zad. 3 – przykład kontraktu POST /inventory/reservations
  analiza/                  LAB2, zad. 1–2 – analiza modułów Oscara i wspólnej bazy danych
  api_przyklady/            LAB2, zad. 3 – przykładowe żądania JSON
  symulacje/                LAB2, zad. 4 – awaria Payment Service i ponowienie z kluczem idempotencji
  docs/                     LAB2, zad. 5 – diagram architektury sklepu
  zrzuty/                   zrzuty ekranu do sprawozdania
  automatyzacja/            skrypty, które wykonały LAB2 i wygenerowały zrzuty oraz sprawozdanie
```

## Pierwsze uruchomienie po sklonowaniu repozytorium (PowerShell)

```
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cd mini-shop
python manage.py rebuild_index --noinput
```

## Uruchomienie (PowerShell)

```
.venv\Scripts\Activate.ps1
cd mini-shop
python manage.py runserver
python ..\analiza\analiza_modulow.py
python ..\analiza\wspolna_baza.py
python ..\symulacje\payment_retry_demo.py
```

Rezerwacja (przy działającym serwerze):

```
curl.exe -s -X POST http://127.0.0.1:8000/inventory/reservations -H "Content-Type: application/json" --data-binary "@..\api_przyklady\rezerwacja_ok.json"
```

`inventory_api` to symulacja kontraktu w monolicie – w laboratorium nie budujemy prawdziwych mikroserwisów.
