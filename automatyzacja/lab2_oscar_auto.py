# -*- coding: utf-8 -*-
"""
LAB2 - Django Oscar jako architektura e-commerce. Automatyzacja + zrzuty ekranu + sprawozdanie.

Uruchomienie (Windows 11, PowerShell, w folderze ze skryptem):

    py lab2_oscar_auto.py

Wymaga plikow lab1_oscar_auto.py, lab2_pliki.py i lab2_diagram.py w tym samym folderze oraz projektu
z LAB1 (domyslnie C:\\Users\\<uzytkownik>\\django-oscar-lab).

Opcje:
    --lab-dir      nowe repozytorium LAB2 (domyslnie C:\\Users\\<uzytkownik>\\django-oscar-lab2)
    --lab1-dir     katalog LAB1 z projektem mini-shop (zrodlo kopii)
    --template     szablon sprawozdania .docx (domyslnie Pulpit\\ecommerce lab2)
    --output       plik wynikowy sprawozdania (domyslnie obok skryptu)
    --port         port serwera deweloperskiego (domyslnie 8000)
    --fresh        usun poprzedni katalog LAB2 i zacznij od nowa
    --report-only  tylko ponownie zbuduj sprawozdanie z istniejacych zrzutow

Skrypt:
  1. tworzy repozytorium django-oscar-lab2 (git init), .venv i kopiuje projekt mini-shop z LAB1,
  2. zad. 1-2: analizuje kod oscar.apps i wspolna baze danych (prawdziwe dane z projektu),
  3. zad. 3: dodaje przyklad kontraktu POST /inventory/reservations i testuje go curl.exe,
  4. zad. 4: pokazuje obsluge bledu platnosci w kodzie Oscara i symuluje awarie Payment Service,
  5. zad. 5: rysuje diagram architektury sklepu,
  6. wstawia zrzuty i odpowiedzi do sprawozdania, nie zmieniajac tabel ani stylow szablonu.
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import lab1_oscar_auto as L1  # noqa: E402
import lab2_pliki as F  # noqa: E402
from lab1_oscar_auto import DevServer, State, code_html, log, run, sub_env  # noqa: E402
from lab2_diagram import diagram_html  # noqa: E402

MARKER = ".lab2_auto"
APPS9 = ["catalogue", "basket", "checkout", "order", "customer", "offer", "shipping", "payment", "partner"]


# --------------------------------------------------------------------------------------
# FAZA 1 (systemowy Python): repozytorium, .venv, kopia projektu z LAB1
# --------------------------------------------------------------------------------------
def phase_setup(args):
    lab, lab1 = args.lab_dir, args.lab1_dir
    if len(str(lab)) > 80:
        raise SystemExit(f"Sciezka {lab} jest za dluga (limit 260 znakow Windows dla plikow w .venv).")
    if not (lab1 / "mini-shop" / "manage.py").exists():
        raise SystemExit(f"Nie znaleziono projektu LAB1 w {lab1}\\mini-shop (uzyj --lab1-dir).")
    if lab.exists():
        if args.fresh and (lab / MARKER).exists():
            log(f"Usuwam poprzedni katalog {lab}")
            shutil.rmtree(lab)
        elif args.fresh:
            raise SystemExit(f"{lab} nie zostal utworzony przez ten skrypt - nie usuwam go.")
        elif not ((lab / "state.json").exists() and (lab / ".venv").exists()):
            raise SystemExit(f"Katalog {lab} juz istnieje. Uzyj --fresh albo innego --lab-dir.")
    parent = lab.parent
    state = State(lab / "state.json")
    if not state.get("setup_done"):
        state.data = {"terminals": {}, "shots": []}
        if not lab.exists():
            run(state, "01_repo", f"mkdir {lab.name}", ["powershell", "-NoProfile", "-Command", f"mkdir '{lab.name}'"],
                parent, venv_prompt=False)
        lab.mkdir(exist_ok=True)
        (lab / MARKER).write_text("utworzone przez lab2_oscar_auto.py", encoding="utf-8")
        state.save()
        terms = state["terminals"]
        terms.setdefault("01_repo", []).append({"prompt": f"PS {parent}>", "cmd": f"cd {lab.name}", "out": "", "keep": None})
        state["terminals"] = terms
        run(state, "01_repo", "git init", ["git", "init"], lab, venv_prompt=False)
        (lab / ".gitignore").write_text(F.GITIGNORE, encoding="utf-8")
        launcher = ["py"] if shutil.which("py") else [sys.executable]
        run(state, "02_venv", "py -m venv .venv", launcher + ["-m", "venv", ".venv"], lab, venv_prompt=False)
        vpy = lab / ".venv" / "Scripts" / "python.exe"
        src_py = lab1 / ".venv" / "Scripts" / "python.exe"
        versions = {"oscar": "4.2.1", "django": "6.1.2"}
        if src_py.exists():  # te same wersje co w projekcie LAB1 (baza i migracje pochodza z LAB1)
            out = subprocess.run([str(src_py), "-c", "import oscar,django;print(oscar.get_version(), django.get_version())"],
                                 capture_output=True, text=True)
            if out.returncode == 0 and len(out.stdout.split()) == 2:
                versions["oscar"], versions["django"] = out.stdout.split()
        spec = [f"django-oscar[sorl-thumbnail]=={versions['oscar']}", f"Django=={versions['django']}", "whoosh==2.7.4",
                "pycountry"]
        run(state, "02_venv", "python -m pip install " + " ".join(f'"{x}"' for x in spec),
            [str(vpy), "-m", "pip", "install"] + spec, lab, keep=8)
        subprocess.run([str(vpy), "-m", "pip", "install", "-q", "playwright"], cwd=lab, check=True)  # tylko do zrzutow
        rel = os.path.relpath(lab1 / "mini-shop", lab)
        run(state, "02_venv", f"Copy-Item -Recurse {rel} .",
            ["powershell", "-NoProfile", "-Command", f"Copy-Item -Recurse '{rel}' .; Get-ChildItem -Name"], lab)
        for junk in (lab / "mini-shop").rglob("__pycache__"):
            shutil.rmtree(junk, ignore_errors=True)
        state["versions"] = versions
        state["started"] = dt.datetime.now().isoformat(timespec="minutes")
        state["setup_done"] = True
    vpy = lab / ".venv" / "Scripts" / "python.exe"
    cmd = [str(vpy), str(Path(__file__).resolve()), "--phase", "main", "--lab-dir", str(lab), "--lab1-dir", str(lab1),
           "--port", str(args.port), "--template", str(args.template), "--output", str(args.output)]
    sys.exit(subprocess.run(cmd, env=sub_env()).returncode)


# --------------------------------------------------------------------------------------
# Pomocnicze
# --------------------------------------------------------------------------------------
def write_files(lab, project):
    files = {
        lab / "analiza" / "analiza_modulow.py": F.ANALIZA_MODULOW,
        lab / "analiza" / "wspolna_baza.py": F.WSPOLNA_BAZA,
        lab / "analiza" / "stan_magazynu.py": F.STAN_MAGAZYNU,
        lab / "api_przyklady" / "rezerwacja_ok.json": F.API_OK,
        lab / "api_przyklady" / "rezerwacja_brak_stanu.json": F.API_BRAK,
        lab / "symulacje" / "payment_retry_demo.py": F.PAYMENT_DEMO,
        lab / "README.md": F.README,
        lab / ".gitignore": F.GITIGNORE,
    }
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def add_inventory_app(project):
    app = project / "inventory_api"
    app.mkdir(exist_ok=True)
    (app / "__init__.py").write_text("", encoding="utf-8")
    (app / "apps.py").write_text(F.INVENTORY_APPS, encoding="utf-8")
    (app / "models.py").write_text(F.INVENTORY_MODELS, encoding="utf-8")
    (app / "views.py").write_text(F.INVENTORY_VIEWS, encoding="utf-8")
    settings = project / "mini_shop" / "settings.py"
    s = settings.read_text(encoding="utf-8")
    if "'inventory_api'" not in s:
        s = s.replace("    'django_tables2',\n",
                      "    'django_tables2',\n\n    'inventory_api',  # LAB2: przyklad kontraktu Inventory Service\n", 1)
        settings.write_text(s, encoding="utf-8")
    urls = project / "mini_shop" / "urls.py"
    u = urls.read_text(encoding="utf-8")
    if "inventory_api" not in u:
        u = u.replace("from django.apps import apps\n",
                      "from django.apps import apps\n\nfrom inventory_api.views import create_reservation\n", 1)
        u = u.replace("    path('admin/', admin.site.urls),\n",
                      "    path('admin/', admin.site.urls),\n"
                      "    path('inventory/reservations', create_reservation, name='inventory-reservations'),\n", 1)
        urls.write_text(u, encoding="utf-8")


def excerpt_rows(path, start, end=None, before=0, after=0, length=None, highlight=()):
    lines = path.read_text(encoding="utf-8").splitlines()
    i = next(n for n, l in enumerate(lines) if start in l) - before
    if end:
        j = next(n for n, l in enumerate(lines) if n > i + before and end in l) + after
    else:
        j = i + length
    return [("add" if any(h in lines[n] for h in highlight) else "ctx", n + 1, lines[n]) for n in range(i, j + 1)]


def file_rows(path, highlight=()):
    return [("add" if any(h in l for h in highlight) else "ctx", n + 1, l)
            for n, l in enumerate(path.read_text(encoding="utf-8").splitlines())]


def py_json(py, script, cwd):
    out = subprocess.run([str(py), str(script), "--json"], cwd=str(cwd), env=sub_env(), capture_output=True,
                         text=True, encoding="utf-8")
    if out.returncode != 0:
        raise SystemExit(out.stdout + out.stderr)
    return json.loads(out.stdout.strip().splitlines()[-1])


def parse_curl(out):
    m = re.search(r"(\{.*\})\s*HTTP (\d{3})", out, re.S)
    return {"http": int(m.group(2)), "body": json.loads(m.group(1))} if m else {"http": None, "body": out}


# --------------------------------------------------------------------------------------
# FAZA 2 (Python z .venv)
# --------------------------------------------------------------------------------------
def phase_main(args):
    from playwright.sync_api import sync_playwright

    lab = args.lab_dir
    state = State(lab / "state.json")
    py = Path(sys.executable)
    project = lab / "mini-shop"
    oscar_apps = lab / ".venv" / "Lib" / "site-packages" / "oscar" / "apps"
    base = f"http://127.0.0.1:{args.port}"
    write_files(lab, project)

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(channel="msedge")
        except Exception:
            browser = pw.chromium.launch(channel="chrome")
        shot = L1.Shooter(state, lab, browser)

        # --- Przygotowanie --------------------------------------------------------------
        shot.terminal("01_repo", "01_repo", "Utworzenie katalogu i nowego repozytorium git dla LAB2", "przyg")
        shot.terminal("02_venv", "02_venv", "Środowisko .venv i kopia projektu mini-shop z laboratorium 1", "przyg")
        if not state.get("prep_done"):
            terms = state["terminals"]
            terms["03_start"] = []
            state["terminals"] = terms
            run(state, "03_start", ".venv\\Scripts\\Activate.ps1",
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                 "& '.venv\\Scripts\\Activate.ps1'; Write-Output ('VIRTUAL_ENV = ' + $env:VIRTUAL_ENV)"], lab, venv_prompt=False)
            terms = state["terminals"]
            terms["03_start"].append({"prompt": f"(.venv) PS {lab}>", "cmd": "cd mini-shop", "out": "", "keep": None})
            state["terminals"] = terms
            run(state, "03_start", "python manage.py check", [str(py), "manage.py", "check"], project)
            state["prep_done"] = True
        shot.terminal("03_start", "03_aktywacja", "Aktywacja środowiska i przejście do katalogu projektu (instrukcja: Przygotowanie projektu)", "przyg")

        # --- Zadanie 1 i 2: analiza modulow i danych -----------------------------------
        if not state.get("analysis_done"):
            for g in ("04_apps", "05_moduly", "06_baza"):
                terms = state["terminals"]
                terms[g] = []
                state["terminals"] = terms
            run(state, "04_apps", "Get-ChildItem ..\\.venv\\Lib\\site-packages\\oscar\\apps -Directory -Name",
                ["powershell", "-NoProfile", "-Command",
                 "Get-ChildItem ..\\.venv\\Lib\\site-packages\\oscar\\apps -Directory -Name | Where-Object { $_ -ne '__pycache__' }"],
                project)
            run(state, "05_moduly", "python ..\\analiza\\analiza_modulow.py",
                [str(py), str(lab / "analiza" / "analiza_modulow.py")], project)
            run(state, "06_baza", "python ..\\analiza\\wspolna_baza.py",
                [str(py), str(lab / "analiza" / "wspolna_baza.py")], project)
            state["modules"] = py_json(py, lab / "analiza" / "analiza_modulow.py", project)
            state["database"] = py_json(py, lab / "analiza" / "wspolna_baza.py", project)
            state["analysis_done"] = True
        shot.terminal("04_apps", "04_oscar_apps", "Aplikacje (obszary) pakietu oscar.apps w środowisku projektu", "zad1")
        shot.terminal("05_moduly", "05_analiza_modulow", "Analiza modułów: modele, rozmiar kodu i zależności między aplikacjami Oscara", "zad1")
        shot.terminal("06_baza", "06_wspolna_baza", "Wspólna baza danych: tabele modułów, klucze obce między modułami i zapytanie łączące order z partner", "zad1")
        shot.html(code_html("oscar/apps/checkout/mixins.py",
                            excerpt_rows(oscar_apps / "checkout" / "mixins.py", "def handle_order_placement", "basket.submit()",
                                         after=6, highlight=("place_order(", "basket.submit()", "handle_successful_order"))),
                  "07_kod_checkout_place_order",
                  "Checkout wywołuje moduły order i basket bezpośrednio w tym samym procesie (oscar/apps/checkout/mixins.py)", "zad1")
        shot.html(code_html("oscar/apps/order/utils.py",
                            excerpt_rows(oscar_apps / "order" / "utils.py", "line.stockrecord.allocate", before=14, length=18,
                                         highlight=("stockrecord.allocate", "def update_stock_records"))),
                  "08_kod_order_allocate",
                  "Moduł order sam zmienia stan magazynu partnera (stockrecord.allocate) – możliwe tylko we wspólnej bazie", "zad2")

        # --- Zadanie 3: kontrakt API ---------------------------------------------------
        add_inventory_app(project)
        shot.html(code_html("mini-shop/inventory_api/views.py",
                            file_rows(project / "inventory_api" / "views.py",
                                      highlight=("def create_reservation", "rejected(409", "rejected(400", "rejected(404",
                                                 "return reserved(", "stock.allocate", "existing"))),
                  "09_kod_inventory_views", "Przykład kontraktu POST /inventory/reservations – widok inventory_api/views.py", "zad3")
        shot.html(code_html("mini-shop/inventory_api/models.py", file_rows(project / "inventory_api" / "models.py",
                                                                           highlight=("product_id", "order_id", "UniqueConstraint"))),
                  "10_kod_inventory_model", "Model Reservation – dane należące do Inventory (identyfikatory zamiast kluczy obcych)", "zad3")
        shot.html(code_html("mini-shop/mini_shop/urls.py", file_rows(project / "mini_shop" / "urls.py", highlight=("inventory",))),
                  "11_kod_urls", "Rejestracja endpointu POST /inventory/reservations w urls.py", "zad3")
        if not state.get("api_migrated"):
            terms = state["terminals"]
            terms["12_migr"] = []
            state["terminals"] = terms
            run(state, "12_migr", "python manage.py makemigrations inventory_api",
                [str(py), "manage.py", "makemigrations", "inventory_api"], project)
            run(state, "12_migr", "python manage.py migrate inventory_api",
                [str(py), "manage.py", "migrate", "inventory_api"], project)
            state["api_migrated"] = True
        shot.terminal("12_migr", "12_migracja_inventory", "Migracja tabeli rezerwacji (inventory_api_reservation)", "zad3")

        url = f"{base}/inventory/reservations"
        curl_tpl = (f'curl.exe -s -w "\\nHTTP %{{http_code}}\\n" -X POST {url} -H "Content-Type: application/json" '
                    '--data-binary "@..\\api_przyklady\\__F__"')

        class _Disp:
            @staticmethod
            def format(f):
                return curl_tpl.replace("__F__", f)

        curl_disp = _Disp
        curl_argv = ["curl.exe", "-s", "-w", "\\nHTTP %{http_code}\\n", "-X", "POST", url,
                     "-H", "Content-Type: application/json", "--data-binary"]
        with DevServer(py, project, args.port, lab / "server1.log"):
            page = browser.new_page(viewport={"width": 1366, "height": 800})
            page.goto(base + "/")
            shot.page(page, "13_sklep_lab2", "Projekt z laboratorium 1 uruchomiony w repozytorium LAB2 (punkt wyjścia analizy)", "przyg")
            page.close()
            terms = state["terminals"]
            terms["14_api"] = []
            state["terminals"] = terms
            run(state, "14_api", "Get-Content ..\\api_przyklady\\rezerwacja_ok.json",
                ["powershell", "-NoProfile", "-Command", "Get-Content ..\\api_przyklady\\rezerwacja_ok.json"], project)
            run(state, "14_api", "python ..\\analiza\\stan_magazynu.py", [str(py), str(lab / "analiza" / "stan_magazynu.py")], project)
            results = {}
            for name, fname in (("ok", "rezerwacja_ok.json"), ("retry", "rezerwacja_ok.json")):
                out = run(state, "14_api", curl_disp.format(f=fname), curl_argv + [f"@..\\api_przyklady\\{fname}"], project)
                results[name] = parse_curl(out)
            terms = state["terminals"]
            terms["15_api"] = []
            state["terminals"] = terms
            run(state, "15_api", "Get-Content ..\\api_przyklady\\rezerwacja_brak_stanu.json",
                ["powershell", "-NoProfile", "-Command", "Get-Content ..\\api_przyklady\\rezerwacja_brak_stanu.json"], project)
            out = run(state, "15_api", curl_disp.format(f="rezerwacja_brak_stanu.json"),
                      curl_argv + ["@..\\api_przyklady\\rezerwacja_brak_stanu.json"], project)
            results["brak"] = parse_curl(out)
            run(state, "15_api", "python ..\\analiza\\stan_magazynu.py", [str(py), str(lab / "analiza" / "stan_magazynu.py")], project)
            state["api"] = results
        shot.terminal("14_api", "14_api_rezerwacja_udana",
                      "Rezerwacja udana (HTTP 201) i ponowienie tego samego żądania (HTTP 200, ta sama rezerwacja)", "zad3")
        shot.terminal("15_api", "15_api_brak_stanu", "Brak wystarczającego stanu (HTTP 409 insufficient_stock) i stan magazynu po rezerwacjach", "zad3")

        # --- Zadanie 4: awaria platnosci -----------------------------------------------
        shot.html(code_html("oscar/apps/checkout/views.py",
                            excerpt_rows(oscar_apps / "checkout" / "views.py", "order_number = self.generate_order_number(basket)",
                                         "signals.post_payment.send_robust", before=1,
                                         highlight=("freeze_basket", "self.handle_payment(", "except ", "restore_frozen_basket"))),
                  "16_kod_checkout_payment",
                  "Obsługa błędu płatności w Oscarze: koszyk zamrożony, przy błędzie przywrócony, zamówienie nie powstaje", "zad4")
        terms = state["terminals"]
        terms["17_pay"] = []
        state["terminals"] = terms
        out = run(state, "17_pay", "python ..\\symulacje\\payment_retry_demo.py",
                  [str(py), str(lab / "symulacje" / "payment_retry_demo.py")], project)
        m = re.search(r"bez klucza = (\d+) .*z kluczem = (\d+)", out)
        state["payment_demo"] = {"bez": int(m.group(1)), "z": int(m.group(2))} if m else None
        shot.terminal("17_pay", "17_symulacja_platnosci",
                      "Symulacja: Payment Service nie odpowiada w czasie – ponowienie bez klucza i z kluczem idempotencji", "zad4")

        # --- Zadanie 5: diagram -------------------------------------------------------
        shot.html(diagram_html(), "18_diagram_architektury",
                  "Diagram architektury sklepu: monolit modułowy, wydzielone serwisy, dane, komunikacja sync/async i punkt awarii",
                  "zad5")
        (lab / "docs").mkdir(exist_ok=True)
        shutil.copy2(lab / "zrzuty" / "18_diagram_architektury.png", lab / "docs" / "architektura_sklepu.png")
        (lab / "docs" / "architektura_sklepu.html").write_text(diagram_html(), encoding="utf-8")
        browser.close()

    terms = state["terminals"]
    terms["19_git"] = []
    state["terminals"] = terms
    run(state, "19_git", "git status --short", ["git", "status", "--short"], lab, venv_prompt=True)
    shot_finish(args, state)


def shot_finish(args, state):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(channel="msedge")
        except Exception:
            browser = pw.chromium.launch(channel="chrome")
        shot = L1.Shooter(state, args.lab_dir, browser)
        shot.terminal("19_git", "19_git_status", "Zawartość nowego repozytorium LAB2 (pliki do pierwszego commita)", "przyg")
        browser.close()
    state["finished"] = dt.datetime.now().isoformat(timespec="minutes")
    L1.build_report(args, state, content_fn=report_content)


# --------------------------------------------------------------------------------------
# Tresc sprawozdania
# --------------------------------------------------------------------------------------
RESP = {
    "catalogue": "Katalog: produkty, klasy produktów, kategorie, atrybuty, warianty, zdjęcia, opcje i rekomendacje.",
    "basket": "Koszyk: koszyki klientów (otwarty/zamrożony/złożony), pozycje koszyka, ceny w chwili dodania, vouchery w koszyku.",
    "checkout": "Proces checkout: kolejne kroki (adres, dostawa, płatność, podsumowanie) i złożenie zamówienia z koszyka.",
    "order": "Zamówienia: Order, pozycje, adresy, statusy i ich historia, zdarzenia płatności i wysyłki, numeracja zamówień.",
    "customer": "Klienci: rejestracja i logowanie, konto, książka adresowa, historia zamówień, alerty i powiadomienia.",
    "offer": "Promocje: oferty warunkowe, zakresy produktów, warunki i korzyści (rabaty), naliczanie ich w koszyku.",
    "shipping": "Dostawa: metody wysyłki, ich koszty (np. według wagi) i wybór metody w checkoucie.",
    "payment": "Płatności: źródła i typy płatności, transakcje, karty, wyjątki błędów płatności (bez bramki).",
    "partner": "Partnerzy i magazyn: partnerzy (sprzedawcy), StockRecord (cena, stan, alokacje), strategia cen i dostępności.",
}


def report_content(state):
    mods = {r["app"]: r for r in (state.get("modules") or {}).get("rows", [])}
    db = state.get("database") or {}
    api = state.get("api") or {}
    pay = state.get("payment_demo") or {"bez": 2, "z": 1}
    shots = {s["name"]: s for s in state["shots"]}
    v = state.get("versions") or {"oscar": "?", "django": "?"}
    C = []

    def imgs(*names):
        for n in names:
            if n in shots:
                C.append(("img", n))

    def json_lines(obj):
        return [("t", line) for line in json.dumps(obj, ensure_ascii=False, indent=2).splitlines()]

    fks = db.get("fks", [])
    fk_examples = "; ".join(f"{x['from']} → {x['to']}" for x in fks
                            if x["from"].startswith(("order.Line.", "basket.Line.")) and "option" not in x["from"])
    n_tables = db.get("tables", "?")
    join_rows = db.get("join", [])

    # --- Przygotowanie
    C += [("t", "Laboratorium wykonano lokalnie (Windows 11, PowerShell, Python, virtualenv). Punktem wyjścia jest projekt mini-shop "
                f"z laboratorium 1 (Django Oscar {v['oscar']}, Django {v['django']}, SQLite, wyszukiwarka Whoosh). Dla LAB2 utworzono nowe "
                "repozytorium git django-oscar-lab2 o strukturze z instrukcji (.venv obok katalogu mini-shop), skopiowano do niego "
                "projekt z LAB1 razem z bazą danych i dodano katalogi z analizami (analiza), przykładowymi żądaniami API (api_przyklady), "
                "symulacją awarii płatności (symulacje) i diagramem (docs). Wszystkie kroki wykonano skryptem lab2_oscar_auto.py, "
                "który po każdym etapie zapisał zrzut ekranu z rzeczywistym wynikiem."),
          ("e",),
          ("b", "0. Przygotowanie projektu")]
    imgs("01_repo", "02_venv", "03_aktywacja", "13_sklep_lab2", "19_git_status")

    # --- Zadanie 1
    C += [("e",), ("b", "1. Zadanie 1 – Oscar jako monolit"),
          ("t", "W katalogu .venv\\Lib\\site-packages\\oscar\\apps odnaleziono wszystkie wymagane obszary. Dla każdego z nich skrypt "
                "analiza_modulow.py policzył modele, rozmiar kodu i odwołania do innych aplikacji Oscara (get_model, get_class, importy), "
                f"a wspolna_baza.py pokazał, że wszystkie moduły zapisują dane w jednej bazie ({db.get('db', 'db.sqlite3')}, "
                f"{n_tables} tabel) i są powiązane kluczami obcymi.")]
    imgs("04_oscar_apps", "05_analiza_modulow", "06_wspolna_baza", "07_kod_checkout_place_order")
    rows = [["Obszar", "Za co odpowiada?", "Czy jest modułem? Dlaczego?"]]
    for a in APPS9:
        r = mods.get(a, {"models": [], "deps": []})
        deps = ", ".join(d for d, _ in r["deps"][:3]) or "—"
        n_tab = (db.get("per_app") or {}).get(a, "?")
        if a == "checkout":
            why = ("Tak – moduł monolitu bez własnych tabel; steruje procesem, wywołując order, basket, payment i shipping "
                   f"w tym samym procesie (najczęściej: {deps}).")
        else:
            coop = (f"współpracuje z innymi modułami przez wywołania w kodzie (najczęściej: {deps})" if r["deps"] else
                    "sam nie wywołuje innych modułów, to checkout i basket wywołują go w kodzie")
            why = (f"Tak – moduł (aplikacja Django) monolitu: {n_tab} tabel we wspólnej bazie, ten sam proces i wdrożenie; "
                   f"{coop}.")
        rows.append([a, RESP[a], why])
    C += [("table", rows, [1500, 3600, 3989]), ("e",),
          ("t", "Czy wiele aplikacji Django oznacza mikroserwisy? Nie. Wszystkie aplikacje Oscara działają w jednym procesie "
                "Pythona, korzystają z jednej bazy danych i są wdrażane razem – moduły komunikują się wywołaniami funkcji "
                "(np. checkout wywołuje place_order i basket.submit() bezpośrednio, rys. powyżej), a nie żądaniami sieciowymi. "
                "Oscar jest więc monolitem modułowym: ma dobrze wydzielone moduły, ale nie są to osobne, niezależnie wdrażane "
                "procesy komunikujące się przez sieć, czyli mikroserwisy.")]

    # --- Zadanie 2
    C += [("e",), ("b", "2. Zadanie 2 – Kto jest właścicielem danych?"),
          ("table", [["Serwis", "Jego dane"],
                     ["Product Service", "produkty, klasy produktów, atrybuty i warianty, kategorie, opisy, zdjęcia, ceny katalogowe"],
                     ["Order Service", "zamówienia i ich pozycje (z kopią nazwy, ceny i ilości z chwili zakupu), statusy i historia "
                                       "statusów, adres dostawy zamówienia, numer zamówienia, powiązanie z klientem (customer_id)"],
                     ["Inventory Service", "stany magazynowe (ilość na stanie), rezerwacje/alokacje dla zamówień, magazyny, "
                                           "SKU partnera, progi niskiego stanu"],
                     ["Customer Service", "konta klientów, dane kontaktowe (e-mail, telefon), książka adresowa, zgody, preferencje"]],
           [2600, 6489]),
          ("e",),
          ("t", "Odpowiedź: c) Nie, jeżeli Inventory jest osobnym mikroserwisem – powinien udostępnić własny interfejs."),
          ("t", "Uzasadnienie: właścicielem danych magazynowych jest Inventory Service, więc tylko on może je odczytywać i zmieniać – "
                "Order Service pyta o dostępność przez API, dzięki czemu Inventory może zmienić schemat bazy, technologię i reguły "
                "rezerwacji bez psucia innych serwisów."),
          ("t", "W obecnym Oscarze (monolit) jest dokładnie odwrotnie: moduł order sam wywołuje stockrecord.allocate() na tabeli "
                "partner_stockrecord, a koszyk i zamówienie mają klucze obce do tabel partnera i katalogu "
                f"({len(fks)} powiązań między modułami, np. {fk_examples}). Jedno zapytanie SQL łączy tabele order_line "
                f"i partner_stockrecord (w naszej bazie zwraca pozycje zamówień: {len(join_rows)}). We wspólnej bazie jest to wygodne, ale przy "
                "podziale na mikroserwisy każde takie miejsce trzeba zastąpić wywołaniem API lub zdarzeniem.")]
    imgs("08_kod_order_allocate")

    # --- Zadanie 3
    ok, retry, brak = api.get("ok", {}), api.get("retry", {}), api.get("brak", {})
    C += [("e",), ("b", "3. Zadanie 3 – API i komunikacja"),
          ("t", "Kontrakt rezerwacji produktu w Inventory Service:"),
          ("t", "Endpoint: POST /inventory/reservations, Content-Type: application/json"),
          ("t", "Żądanie:")]
    C += json_lines({"product_id": 1, "quantity": 2, "order_id": "2026-00123"})
    C += [("t", "Odpowiedź – rezerwacja udana (HTTP 201 Created):")]
    C += json_lines(ok.get("body") if isinstance(ok.get("body"), dict) else
                    {"reservation_id": "R-00001", "status": "reserved", "product_id": 1, "quantity": 2, "order_id": "2026-00123"})
    C += [("t", "Odpowiedź – brak wystarczającego stanu (HTTP 409 Conflict):")]
    C += json_lines(brak.get("body") if isinstance(brak.get("body"), dict) else
                    {"status": "rejected", "reason": "insufficient_stock", "available": 0})
    C += [("t", "Pozostałe odpowiedzi kontraktu: 400 invalid_request (błędne dane), 404 unknown_product (nieznany produkt). "
                "Ponowienie tego samego żądania (ta sama para order_id + product_id) zwraca istniejącą rezerwację z kodem 200 "
                f"i nie rezerwuje towaru drugi raz (w teście: HTTP {retry.get('http', 200)}, "
                f"{(retry.get('body') or {}).get('reservation_id', 'R-00001') if isinstance(retry.get('body'), dict) else 'R-00001'}). "
                "Rezerwacja wygasa po 15 minutach (expires_at), jeśli zamówienie nie zostanie potwierdzone."),
          ("t", "Kontrakt zaimplementowano jako przykład w projekcie (aplikacja inventory_api) i przetestowano poleceniem curl.exe. "
                "To symulacja interfejsu w monolicie – zgodnie z instrukcją nie budujemy prawdziwych mikroserwisów. Model Reservation "
                "przechowuje product_id i order_id jako zwykłe identyfikatory, a nie klucze obce, bo serwis magazynu nie powinien "
                "sięgać do tabel katalogu ani zamówień.")]
    imgs("09_kod_inventory_views", "10_kod_inventory_model", "11_kod_urls", "12_migracja_inventory",
         "14_api_rezerwacja_udana", "15_api_brak_stanu")
    C += [("t", "Decyzja: rezerwacja podczas checkoutu powinna być synchroniczna (a). Checkout musi przed płatnością wiedzieć, "
                "czy towar jest dostępny – inaczej klient zapłaciłby za produkt, którego nie ma. Wywołanie jest krótkie i klient "
                "i tak czeka na wynik; stosujemy krótki timeout (np. 2 s), a przy błędzie lub braku odpowiedzi pokazujemy komunikat "
                "i nie przechodzimy do płatności. Potwierdzenie albo zwolnienie rezerwacji po złożeniu lub anulowaniu zamówienia "
                "może już odbywać się asynchronicznie (zdarzenie)."),
          ("table", [["Sytuacja", "Sync / Async", "Uzasadnienie"],
                     ["Checkout → Payment: „czy płatność się udała?”", "Sync",
                      "klient czeka na wynik, od niego zależy utworzenie zamówienia (wynik końcowy można dodatkowo potwierdzić webhookiem)"],
                     ["OrderCreated → Fulfillment", "Async",
                      "realizacja trwa godziny/dni; zdarzenie przez broker nie blokuje checkoutu i przetrwa chwilową awarię magazynu"],
                     ["Order → Inventory: rezerwacja produktu", "Sync",
                      "potrzebna natychmiastowa odpowiedź (reserved/rejected) przed płatnością"],
                     ["OrderCreated → wysłanie e-maila", "Async",
                      "e-mail nie wpływa na wynik zakupu; można go ponowić później, awaria serwera poczty nie psuje zamówienia"]],
           [3200, 1300, 4589])]

    # --- Zadanie 4
    C += [("e",), ("b", "4. Zadanie 4 – Co, jeśli Payment Service nie działa?"),
          ("t", "1. Czy tworzymy Order? Nie tworzymy zamówienia jako złożonego. Tak działa Oscar: w PaymentDetailsView.submit() "
                "najpierw zamraża koszyk i wywołuje handle_payment(), a place_order() wykonuje dopiero po udanej płatności; przy wyjątku "
                "zamówienie nie powstaje. Zapisujemy jedynie próbę płatności (numer zamówienia, klucz idempotencji, status „nieznany”)."),
          ("t", "2. Czy klient powinien zobaczyć komunikat? Tak – zrozumiały komunikat bez szczegółów technicznych, np. „Nie udało się "
                "potwierdzić płatności. Jeśli środki zostały pobrane, zamówienie zostanie potwierdzone automatycznie albo pieniądze "
                "wrócą na konto.” Oscar w tym miejscu wyświetla błąd i wraca do kroku płatności."),
          ("t", "3. Czy pieniądze mogły zostać pobrane? Tak. Brak odpowiedzi (timeout) nie oznacza odmowy: żądanie mogło dotrzeć "
                "do Payment Service i zostać zrealizowane, a zgubiona została tylko odpowiedź. Dlatego status płatności jest „nieznany” "
                "i trzeba go wyjaśnić – zapytaniem o status albo webhookiem od bramki. Uwaga: domyślny komunikat Oscara przy "
                "PaymentError brzmi „no payment has been taken” (rys. poniżej, linie 604–607) – przy timeoucie może to być "
                "nieprawda, dlatego w integracji z bramką warto go zmienić na komunikat o nieznanym statusie płatności."),
          ("t", "4. Co z koszykiem? Koszyk nie może zostać utracony ani podwojony. Oscar podczas płatności zamraża koszyk "
                "(freeze_basket), a przy błędzie przywraca go (restore_frozen_basket) – klient wraca do checkoutu z tymi samymi "
                "produktami. Rezerwacja w Inventory jest utrzymywana do czasu wygaśnięcia (expires_at) i zwalniana, jeśli płatność "
                "ostatecznie się nie powiedzie."),
          ("t", "Zasada ponowienia płatności: każda próba zapłaty za dane zamówienie ma jeden klucz idempotencji (Idempotency-Key, "
                "np. payment-<numer zamówienia>-<nr próby zapłaty>) i każde ponowienie wysyłamy z tym samym kluczem. Payment Service "
                "zapamiętuje wynik dla klucza i przy powtórzeniu zwraca istniejący wynik zamiast obciążać klienta ponownie. Przed "
                "ponowieniem sprawdzamy status płatności, ponawiamy najwyżej kilka razy z rosnącym odstępem (np. 1 s, 2 s, 4 s), "
                "a nowy klucz tworzymy dopiero po jednoznacznej odmowie płatności.")]
    imgs("16_kod_checkout_payment", "17_symulacja_platnosci")
    C += [("t", f"Symulacja potwierdza zasadę: Payment Service pobrał pieniądze, ale odpowiedział po czasie. Ponowienie bez klucza "
                f"dało {pay['bez']} obciążenia klienta (podwójna płatność), a ponowienie z tym samym kluczem idempotencji – "
                f"{pay['z']} obciążenie (druga odpowiedź to powtórzenie wyniku pierwszej próby).")]

    # --- Zadanie 5
    C += [("e",), ("b", "5. Zadanie 5 – Projekt architektury sklepu"),
          ("t", "Scenariusz: 100 tys. produktów, koszyk, płatności online, magazyn, dostawa kurierska, konta klientów i zwroty."),
          ("t", "1. Moduły jednego monolitu (Django Oscar): Product (katalog), Cart (koszyk), Order (zamówienia z checkoutem), Customer "
                "(konta), Returns (zwroty) oraz promocje. Są silnie powiązane w jednym procesie zakupowym, więc wspólne wdrożenie "
                "i transakcje w jednej bazie upraszczają system; granice modułów zostają zachowane w kodzie."),
          ("t", "2. Wydzielone serwisy: Payment Service (integracja z bramką, bezpieczeństwo, idempotencja, osobne wymagania PCI), "
                "Inventory Service (stany i rezerwacje, wiele magazynów, duża liczba aktualizacji), Delivery Service (integracje "
                "z kurierami, etykiety, statusy przesyłek) oraz wyszukiwarka Elasticsearch dla 100 tys. produktów i worker powiadomień."),
          ("t", "3. Właściciele danych: monolit – wspólna baza PostgreSQL z osobnym schematem każdego modułu (moduł zapisuje tylko "
                "swoje tabele); Payment, Inventory i Delivery mają własne bazy, a inne komponenty znają ich dane wyłącznie przez API "
                "lub zdarzenia; indeks wyszukiwarki to kopia danych katalogu odbudowywana ze zdarzeń."),
          ("t", "4. Komunikacja synchroniczna: klient → API Gateway → monolit (HTTPS), checkout → Inventory (rezerwacja), checkout → "
                "Payment (autoryzacja płatności), Payment → bramka płatnicza, Delivery → API kuriera."),
          ("t", "5. Komunikacja asynchroniczna (broker zdarzeń): OrderCreated → Delivery i powiadomienia e-mail, ReturnApproved → "
                "zwrot pieniędzy w Payment, ProductUpdated → indeksowanie w wyszukiwarce, webhook bramki → potwierdzenie płatności."),
          ("t", "6. Punkt awarii: Payment Service i zewnętrzna bramka płatnicza – brak odpowiedzi blokuje złożenie zamówienia, a status "
                "płatności jest nieznany (obsługa jak w zadaniu 4: timeout, idempotencja, webhook, uzgadnianie statusów). Kolejnymi "
                "punktami są broker zdarzeń (kolejka z trwałymi wiadomościami i ponowieniami) oraz API kuriera.")]
    imgs("18_diagram_architektury")
    C += [("table", [["Komponent", "Monolit / serwis", "Właściciel danych", "Komunikacja"],
                     ["Product, Cart, Order, Customer, Returns, Offer", "moduły monolitu", "własne schematy we wspólnej bazie",
                      "wywołania w procesie; na zewnątrz HTTP przez API Gateway"],
                     ["Payment", "osobny serwis", "własna baza płatności", "sync z checkoutu; webhook i refund async"],
                     ["Inventory", "osobny serwis", "własna baza magazynu", "sync rezerwacja; zwolnienie/potwierdzenie async"],
                     ["Delivery", "osobny serwis", "własna baza przesyłek", "async OrderCreated; sync do API kuriera"],
                     ["Wyszukiwarka, powiadomienia", "komponenty pomocnicze", "kopia danych (indeks) / brak", "async ze zdarzeń"]],
           [2600, 1700, 2300, 2489])]

    # --- Pytanie dodatkowe
    C += [("e",), ("b", "6. Pytanie dodatkowe – distributed monolith"),
          ("t", "Nie. Taki podział daje wszystkie koszty mikroserwisów (sieć, opóźnienia, nowe rodzaje awarii, trudniejsze wdrożenie "
                "i monitorowanie), ale żadnej z ich zalet. Wspólna baza oznacza brak własności danych – zmiana tabeli jednego serwisu "
                "psuje inne; synchroniczny łańcuch wywołań sprawia, że awaria lub spowolnienie jednej usługi zatrzymuje cały request; "
                "konieczność wspólnego wdrażania znosi niezależność zespołów i wydań."),
          ("t", "Distributed monolith (monolit rozproszony) to system podzielony na wiele osobno uruchamianych usług, które są jednak "
                "tak silnie sprzężone (wspólna baza, synchroniczne zależności, wspólne wdrożenia, współdzielone modele danych), że "
                "w praktyce zachowują się jak jeden monolit – tyle że rozproszony po sieci, a więc wolniejszy i bardziej awaryjny. "
                "Lepszym wyjściem jest wtedy dobrze zaprojektowany monolit modułowy, jak Oscar.")]
    conclusions = [
        "Django Oscar to monolit modułowy: ma wyraźnie wydzielone aplikacje (catalogue, basket, checkout, order, customer, offer, "
        "shipping, payment, partner), ale działają one w jednym procesie, na jednej bazie i są wdrażane razem.",
        "Wiele aplikacji Django nie oznacza wielu mikroserwisów – o mikroserwisie decyduje osobny proces, własne dane i komunikacja przez sieć.",
        "Mikroserwis musi mieć własną odpowiedzialność i granicę danych; jeżeli Inventory jest osobnym serwisem, Order korzysta "
        "z jego API (np. POST /inventory/reservations), a nie z tabel magazynu – w Oscarze order robi to bezpośrednio.",
        "Komunikacja sieciowa wprowadza nowe rodzaje awarii: timeout nie oznacza odmowy, dlatego płatności wymagają kluczy "
        "idempotencji, a koszyk musi przetrwać nieudaną płatność.",
        "Komunikacja synchroniczna jest prosta, ale uzależnia dostępność komponentów; asynchroniczna zmniejsza sprzężenie, "
        "ale utrudnia śledzenie procesu.",
        "Mikroserwisy nie są automatycznie lepsze od monolitu – architektura to kompromis między prostotą, niezależnością, "
        "spójnością danych i złożonością operacyjną; źle podzielony system staje się distributed monolith.",
    ]
    return C, conclusions


# --------------------------------------------------------------------------------------
def main():
    home = Path.home()
    ap = argparse.ArgumentParser(description="LAB2 Django Oscar - architektura: automatyzacja + zrzuty + sprawozdanie")
    ap.add_argument("--lab-dir", type=Path, default=home / "django-oscar-lab2")
    ap.add_argument("--lab1-dir", type=Path, default=home / "django-oscar-lab")
    ap.add_argument("--template", type=Path, default=home / "Desktop" / "ecommerce lab2" / "Załącznik_2_Szablon_sprawozdania.docx")
    ap.add_argument("--output", type=Path, default=SCRIPT_DIR / "Sprawozdanie_LAB2_Django_Oscar.docx")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--phase", default="setup", choices=["setup", "main"])
    args = ap.parse_args()
    args.lab_dir = args.lab_dir.resolve()
    args.lab1_dir = args.lab1_dir.resolve()
    if args.report_only:
        L1.build_report(args, State(args.lab_dir / "state.json"), content_fn=report_content)
    elif args.phase == "setup":
        phase_setup(args)
    else:
        phase_main(args)


if __name__ == "__main__":
    main()
