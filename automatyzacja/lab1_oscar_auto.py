# -*- coding: utf-8 -*-
"""
LAB1 - Django Oscar: wlasny mini-sklep. Pelna automatyzacja instrukcji + zrzuty ekranu
+ wygenerowanie sprawozdania na podstawie szablonu (Zalacznik 2).

Uruchomienie (Windows 11, PowerShell, w folderze ze skryptem):

    py lab1_oscar_auto.py --lab-dir C:\\Users\\<uzytkownik>\\django-oscar-lab

Wymagania: Python 3.12+ (launcher "py"), Microsoft Edge lub Google Chrome, internet (pip).
Sciezka katalogu laboratorium musi byc krotka (limit 260 znakow Windows dla plikow w .venv).
Hasla testowe (admin i klient) sa zapisywane w <lab-dir>\\dane_testowe.txt.

Opcje:
    --lab-dir    katalog roboczy laboratorium (domyslnie .\\django-oscar-lab obok skryptu)
    --template   szablon sprawozdania .docx (domyslnie z folderu Pobrane)
    --output     plik wynikowy sprawozdania (domyslnie obok skryptu)
    --port       port serwera deweloperskiego (domyslnie 8000)
    --fresh      usun poprzedni katalog laboratorium i zacznij od nowa
    --headed     pokazuj okno przegladarki podczas automatyzacji
    --report-only  tylko ponownie zbuduj sprawozdanie z istniejacych zrzutow

Skrypt:
  1. tworzy katalog django-oscar-lab, srodowisko .venv i instaluje django-oscar[sorl-thumbnail],
  2. tworzy projekt mini_shop, konfiguruje Oscara (settings.py, urls.py), wykonuje migracje,
  3. tworzy superusera, wykonuje oscar_populate_countries,
  4. przez przegladarke (Playwright + Microsoft Edge) wykonuje czynnosci w dashboardzie i sklepie:
     klasa produktu, partner, kategoria, produkt, warianty, koszyk, checkout, zamowienie,
  5. po kazdym etapie robi zrzut ekranu (przegladarka lub okno terminala z rzeczywistym wyjsciem),
  6. wstawia zrzuty i odpowiedzi do sprawozdania, nie zmieniajac tabel ani stylow szablonu.
"""
import argparse
import datetime as dt
import difflib
import html
import json
import os
import re
import secrets
import shutil
import socket
import string
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
MARKER = ".lab1_auto"
PIP_EXTRA = ["playwright", "pycountry"]  # narzedzia skryptu (zrzuty) i wymaganie oscar_populate_countries

# --------------------------------------------------------------------------------------
# Konfiguracja Oscara wg instrukcji (Etap 3 i 4)
# --------------------------------------------------------------------------------------
INSTALLED_APPS = """INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.flatpages',

    'oscar.config.Shop',
    'oscar.apps.analytics.apps.AnalyticsConfig',
    'oscar.apps.checkout.apps.CheckoutConfig',
    'oscar.apps.address.apps.AddressConfig',
    'oscar.apps.shipping.apps.ShippingConfig',
    'oscar.apps.catalogue.apps.CatalogueConfig',
    'oscar.apps.catalogue.reviews.apps.CatalogueReviewsConfig',
    'oscar.apps.communication.apps.CommunicationConfig',
    'oscar.apps.partner.apps.PartnerConfig',
    'oscar.apps.basket.apps.BasketConfig',
    'oscar.apps.payment.apps.PaymentConfig',
    'oscar.apps.offer.apps.OfferConfig',
    'oscar.apps.order.apps.OrderConfig',
    'oscar.apps.customer.apps.CustomerConfig',
    'oscar.apps.search.apps.SearchConfig',
    'oscar.apps.voucher.apps.VoucherConfig',
    'oscar.apps.wishlists.apps.WishlistsConfig',
    'oscar.apps.dashboard.apps.DashboardConfig',
    'oscar.apps.dashboard.reports.apps.ReportsDashboardConfig',
    'oscar.apps.dashboard.users.apps.UsersDashboardConfig',
    'oscar.apps.dashboard.orders.apps.OrdersDashboardConfig',
    'oscar.apps.dashboard.catalogue.apps.CatalogueDashboardConfig',
    'oscar.apps.dashboard.offers.apps.OffersDashboardConfig',
    'oscar.apps.dashboard.partners.apps.PartnersDashboardConfig',
    'oscar.apps.dashboard.pages.apps.PagesDashboardConfig',
    'oscar.apps.dashboard.ranges.apps.RangesDashboardConfig',
    'oscar.apps.dashboard.reviews.apps.ReviewsDashboardConfig',
    'oscar.apps.dashboard.vouchers.apps.VouchersDashboardConfig',
    'oscar.apps.dashboard.communications.apps.CommunicationsDashboardConfig',
    'oscar.apps.dashboard.shipping.apps.ShippingDashboardConfig',

    'widget_tweaks',
    'haystack',
    'treebeard',
    'sorl.thumbnail',
    'django_tables2',
]

SITE_ID = 1"""

CONTEXT_PROCESSORS = """
                'oscar.apps.search.context_processors.search_form',
                'oscar.apps.checkout.context_processors.checkout',
                'oscar.apps.communication.notifications.context_processors.notifications',
                'oscar.core.context_processors.metadata',"""

MIDDLEWARE_ADD = """
    'oscar.apps.basket.middleware.BasketMiddleware',
    'django.contrib.flatpages.middleware.FlatpageFallbackMiddleware',"""

DATABASES = """DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'ATOMIC_REQUESTS': True,
    }
}"""

SETTINGS_TAIL = """
AUTHENTICATION_BACKENDS = (
    'oscar.apps.customer.auth_backends.EmailBackend',
    'django.contrib.auth.backends.ModelBackend',
)

HAYSTACK_CONNECTIONS = {
    'default': {
        # SimpleEngine z instrukcji nie obsluguje filtrow listy katalogu (All products = 0 wynikow),
        # dlatego uzywamy Whoosh - lokalnego indeksu w plikach.
        'ENGINE': 'haystack.backends.whoosh_backend.WhooshEngine',
        'PATH': BASE_DIR / 'whoosh_index',
    },
}
# aktualizacja indeksu przy kazdym zapisie produktu w dashboardzie
HAYSTACK_SIGNAL_PROCESSOR = 'haystack.signals.RealtimeSignalProcessor'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

OSCAR_INITIAL_ORDER_STATUS = 'Pending'
OSCAR_INITIAL_LINE_STATUS = 'Pending'
OSCAR_ORDER_STATUS_PIPELINE = {
    'Pending': ('Being processed', 'Cancelled'),
    'Being processed': ('Processed', 'Cancelled'),
    'Processed': (),
    'Cancelled': (),
}

# Ceny w laboratorium podajemy w PLN (np. 2999.00 PLN)
OSCAR_DEFAULT_CURRENCY = 'PLN'
"""

URLS_PY = """from django.contrib import admin
from django.urls import include, path
from django.apps import apps

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include(apps.get_app_config('oscar').urls[0])),
]
"""

# Dane produktu z instrukcji
CATEGORY = "Laptopy"
PRODUCT_CLASS = "Laptop"
PARTNER = "TechShop"
PRODUCT = {"title": "Laptop Lenovo ThinkBook", "sku": "TB-001", "price": "2999.00", "stock": "10"}
PARENT_PRODUCT = "ThinkBook"
VARIANTS = [
    {"title": "ThinkBook 16 GB / 512 GB", "ram": "16 GB", "ssd": "512 GB", "sku": "TB-16-512", "price": "3299.00", "stock": "5"},
    {"title": "ThinkBook 16 GB / 1 TB", "ram": "16 GB", "ssd": "1 TB", "sku": "TB-16-1TB", "price": "3599.00", "stock": "4"},
    {"title": "ThinkBook 32 GB / 1 TB", "ram": "32 GB", "ssd": "1 TB", "sku": "TB-32-1TB", "price": "4199.00", "stock": "3"},
]
BASKET_QTY = 2
CUSTOMER = {"first_name": "Jan", "last_name": "Kowalski", "email": "jan.kowalski@example.com",
            "line1": "ul. Testowa 1", "city": "Warszawa", "postcode": "00-001", "phone": "+48500100200"}
ADMIN_EMAIL = "admin@example.com"
ADMIN_USERNAME = "admin"


def log(msg):
    print(f"[LAB1] {msg}", flush=True)


def gen_password():
    alphabet = string.ascii_letters + string.digits
    return "Lab1-" + "".join(secrets.choice(alphabet) for _ in range(12))


# --------------------------------------------------------------------------------------
# Stan pomiedzy fazami (systemowy Python -> Python z .venv)
# --------------------------------------------------------------------------------------
class State:
    def __init__(self, path: Path):
        self.path = path
        self.data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def __getitem__(self, k):
        return self.data[k]

    def get(self, k, d=None):
        return self.data.get(k, d)

    def __setitem__(self, k, v):
        self.data[k] = v
        self.save()

    def save(self):
        if not self.path.parent.exists():
            return
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------------------
# Uruchamianie polecen z zapisem wyjscia (do zrzutow "terminala")
# --------------------------------------------------------------------------------------
def sub_env():
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "0"
    return env


def run(state, group, display_cmd, argv, cwd, env=None, check=True, venv_prompt=True, keep=None):
    """Uruchamia polecenie, zapisuje (prompt, polecenie, wyjscie) do grupy terminala."""
    log(f"$ {display_cmd}")
    p = subprocess.run(argv, cwd=str(cwd), env=env or sub_env(), stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    out = p.stdout.replace("\r\n", "\n")
    out = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", out)
    terms = state.get("terminals", {})
    terms.setdefault(group, []).append({
        "prompt": ("(.venv) " if venv_prompt else "") + f"PS {cwd}>",
        "cmd": display_cmd, "out": out, "keep": keep})
    state["terminals"] = terms
    if check and p.returncode != 0:
        print(out)
        raise SystemExit(f"Polecenie zakonczone bledem ({p.returncode}): {display_cmd}")
    return out


def port_free(port):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


class DevServer:
    """python manage.py runserver uruchomiony w tle (z zapisem logu do zrzutu terminala)."""

    def __init__(self, py, project_dir, port, logfile):
        self.py, self.project_dir, self.port, self.logfile = py, project_dir, port, logfile
        self.proc = None

    def __enter__(self):
        if not port_free(self.port):
            raise SystemExit(f"Port {self.port} jest zajety - zamknij inny serwer albo uzyj --port.")
        self.fh = open(self.logfile, "w", encoding="utf-8")
        args = [str(self.py), "manage.py", "runserver", f"127.0.0.1:{self.port}", "--noreload"]
        self.proc = subprocess.Popen(args, cwd=str(self.project_dir), env=sub_env(), stdout=self.fh,
                                     stderr=subprocess.STDOUT)
        url = f"http://127.0.0.1:{self.port}/"
        for _ in range(120):
            try:
                urllib.request.urlopen(url, timeout=2)
                break
            except urllib.error.HTTPError:
                break
            except Exception:
                if self.proc.poll() is not None:
                    raise SystemExit("Serwer Django nie wystartowal:\n" + Path(self.logfile).read_text())
                time.sleep(0.5)
        return self

    def __exit__(self, *exc):
        self.proc.terminate()
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.fh.close()

    def output(self):
        txt = Path(self.logfile).read_text(encoding="utf-8", errors="replace")
        return txt.rstrip() + "\n^C"


# --------------------------------------------------------------------------------------
# FAZA 1 (systemowy Python): katalog, .venv, instalacja pakietow
# --------------------------------------------------------------------------------------
def phase_setup(args):
    lab = args.lab_dir
    if len(str(lab)) > 80:
        raise SystemExit(f"Sciezka {lab} jest za dluga (Windows ma limit 260 znakow dla plikow w .venv).\n"
                         "Uzyj krotszej, np.: py lab1_oscar_auto.py --lab-dir C:\\Users\\<uzytkownik>\\django-oscar-lab")
    if lab.exists():
        if args.fresh and (lab / MARKER).exists():
            log(f"Usuwam poprzedni katalog {lab}")
            shutil.rmtree(lab)
        elif args.fresh:
            raise SystemExit(f"{lab} nie zostal utworzony przez ten skrypt - nie usuwam go.")
        elif (lab / "state.json").exists() and (lab / ".venv").exists():
            log("Katalog laboratorium istnieje - kontynuuje (uzyj --fresh, aby zaczac od nowa).")
        else:
            raise SystemExit(f"Katalog {lab} juz istnieje. Uzyj --fresh albo innego --lab-dir.")
    parent = lab.parent
    parent.mkdir(parents=True, exist_ok=True)
    state = State(lab / "state.json")
    if not state.get("setup_done"):
        state.data = {"terminals": {}}
        if not lab.exists():
            run(state, "01_mkdir", f"mkdir {lab.name}",
                ["powershell", "-NoProfile", "-Command", f"mkdir '{lab.name}'"], parent, venv_prompt=False)
        lab.mkdir(exist_ok=True)
        (lab / MARKER).write_text("utworzone przez lab1_oscar_auto.py", encoding="utf-8")
        state.save()
        state["started"] = dt.datetime.now().isoformat(timespec="minutes")
        state["admin_password"] = gen_password()
        state["customer_password"] = gen_password()
        state["shots"] = []
        (lab / "zrzuty").mkdir(exist_ok=True)
        # dane testowe w pliku projektu (nie wypisujemy hasel w konsoli)
        (lab / "dane_testowe.txt").write_text(
            "Dane testowe wygenerowane przez lab1_oscar_auto.py (tylko lokalnie)\n"
            f"Dashboard: http://127.0.0.1:{args.port}/dashboard/\n"
            f"Administrator: {ADMIN_EMAIL} / {state['admin_password']}\n"
            f"Klient: {CUSTOMER['email']} / {state['customer_password']}\n", encoding="utf-8")

        terms = state["terminals"]
        for e in terms.get("01_mkdir", []):
            e["prompt"] = f"PS {parent}>"
        terms.setdefault("01_mkdir", []).append({"prompt": f"PS {parent}>", "cmd": f"cd {lab.name}", "out": "", "keep": None})
        state["terminals"] = terms
        launcher = ["py"] if shutil.which("py") else [sys.executable]
        run(state, "02_venv", "py -m venv .venv", launcher + ["-m", "venv", ".venv"], lab, venv_prompt=False)
        run(state, "02_venv", ".venv\\Scripts\\Activate.ps1",
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
             "& '.venv\\Scripts\\Activate.ps1'; Write-Output ('VIRTUAL_ENV = ' + $env:VIRTUAL_ENV)"],
            lab, venv_prompt=False)
        vpy = lab / ".venv" / "Scripts" / "python.exe"
        run(state, "02_venv", "python --version; (Get-Command python).Source",
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
             "& '.venv\\Scripts\\Activate.ps1'; python --version; (Get-Command python).Source"], lab)
        run(state, "03_pip", "python -m pip install --upgrade pip",
            [str(vpy), "-m", "pip", "install", "--upgrade", "pip"], lab, keep=12)
        spec = "django-oscar[sorl-thumbnail]" + (f"=={args.oscar_version}" if args.oscar_version else "")
        run(state, "03_pip", f'python -m pip install "{spec}"',
            [str(vpy), "-m", "pip", "install", spec], lab, keep=14)
        run(state, "03_pip", 'python -m pip install "whoosh<2.8"',
            [str(vpy), "-m", "pip", "install", "whoosh<2.8"], lab, keep=6)
        # narzedzia potrzebne do automatyzacji (nie sa czescia instrukcji - bez zrzutu)
        subprocess.run([str(vpy), "-m", "pip", "install", "-q"] + PIP_EXTRA, cwd=lab, check=True)
        run(state, "04_pipshow", "python -m pip show django-oscar",
            [str(vpy), "-m", "pip", "show", "django-oscar"], lab)
        state["setup_done"] = True
    # FAZA 2 w Pythonie z .venv (tam jest Playwright i Django)
    vpy = lab / ".venv" / "Scripts" / "python.exe"
    cmd = [str(vpy), str(Path(__file__).resolve()), "--phase", "main", "--lab-dir", str(lab),
           "--port", str(args.port), "--template", str(args.template), "--output", str(args.output)]
    if args.headed:
        cmd.append("--headed")
    r = subprocess.run(cmd, env=sub_env())
    sys.exit(r.returncode)


# --------------------------------------------------------------------------------------
# Renderowanie "terminala" i podgladu kodu do PNG (przez Playwright)
# --------------------------------------------------------------------------------------
TERM_CSS = """
body{margin:0;background:#1f1f1f;font-family:'Segoe UI',sans-serif}
.win{width:1180px;border:1px solid #3a3a3a;background:#0c0c0c}
.bar{height:34px;background:#202020;display:flex;align-items:center;color:#ddd;font-size:13px}
.tab{background:#0c0c0c;height:34px;padding:0 18px;display:flex;align-items:center;gap:8px;border-right:1px solid #333}
.ico{width:14px;height:14px;background:#012456;border:1px solid #4d7cc9;display:inline-block;font-size:9px;color:#fff;text-align:center;line-height:14px}
.ctl{margin-left:auto;display:flex;gap:28px;padding-right:18px;color:#aaa;font-size:14px}
pre{margin:0;padding:12px 14px 16px;color:#cccccc;font:14px/1.38 'Cascadia Mono',Consolas,monospace;white-space:pre-wrap;word-break:break-all}
.pr{color:#cccccc}.venv{color:#13a10e}.cmd{color:#f9f1a5}.dim{color:#767676}
"""

CODE_CSS = """
body{margin:0;background:#1e1e1e;font-family:'Segoe UI',sans-serif}
.win{width:1180px;background:#1e1e1e;border:1px solid #333}
.bar{height:32px;background:#2d2d2d;color:#ccc;font-size:13px;display:flex;align-items:center;padding-left:14px;gap:10px}
.file{background:#1e1e1e;height:32px;display:flex;align-items:center;padding:0 16px;border-top:1px solid #0078d4;color:#fff}
table{border-collapse:collapse;font:13.5px/1.45 'Cascadia Mono',Consolas,monospace;width:100%}
td.n{color:#6e7681;text-align:right;padding:0 14px 0 10px;width:36px;user-select:none}
td.c{color:#d4d4d4;white-space:pre-wrap;padding-right:12px}
tr.add td.c{background:#1b3b24}tr.add td.n{background:#1b3b24;color:#8fd19e}
tr.gap td{color:#6e7681;background:#252526;padding:2px 10px;font-style:italic}
.s{color:#ce9178}.k{color:#569cd6}.cm{color:#6a9955}
"""


def _hl(line):
    t = html.escape(line, quote=False)
    t = re.sub(r"\b(from|import|True|False|None)\b", r'<span class="k">\1</span>', t)
    t = re.sub(r"('[^']*')", r'<span class="s">\1</span>', t)
    t = re.sub(r"^(\s*#.*)$", r'<span class="cm">\1</span>', t)
    return t


def term_html(entries, title="Windows PowerShell"):
    parts = []
    for e in entries:
        out = e["out"].rstrip("\n")
        lines = out.split("\n") if out else []
        keep = e.get("keep")
        if keep and len(lines) > keep:
            head = lines[:3]
            tail = lines[-(keep - 3):]
            skipped = len(lines) - len(head) - len(tail)
            lines = head + [f"\x00[... pominięto {skipped} wierszy wyjścia ...]"] + tail
        prompt = e["prompt"]
        pr = html.escape(prompt)
        pr = pr.replace("(.venv) ", '<span class="venv">(.venv)</span> ')
        body = "\n".join(f'<span class="dim">{html.escape(l[1:])}</span>' if l.startswith("\x00")
                         else html.escape(l) for l in lines)
        parts.append(f'<span class="pr">{pr}</span> <span class="cmd">{html.escape(e["cmd"])}</span>'
                     + ("\n" + body if body else ""))
    last_prompt = html.escape(entries[-1]["prompt"]).replace("(.venv) ", '<span class="venv">(.venv)</span> ')
    content = "\n".join(parts) + f"\n{last_prompt} "
    return (f"<html><head><meta charset='utf-8'><style>{TERM_CSS}</style></head><body>"
            f"<div class='win' id='w'><div class='bar'><div class='tab'><span class='ico'>&gt;_</span>{title}</div>"
            f"<div class='ctl'><span>&#8212;</span><span>&#9744;</span><span>&#10005;</span></div></div>"
            f"<pre>{content}</pre></div></body></html>")


def code_html(filename, rows):
    trs = []
    for kind, num, text in rows:
        if kind == "gap":
            trs.append(f"<tr class='gap'><td colspan='2'>{html.escape(text)}</td></tr>")
        else:
            trs.append(f"<tr class='{kind}'><td class='n'>{num}</td><td class='c'>{_hl(text)}</td></tr>")
    return (f"<html><head><meta charset='utf-8'><style>{CODE_CSS}</style></head><body><div class='win' id='w'>"
            f"<div class='bar'><span>Visual Studio Code</span><span class='file'>{html.escape(filename)}</span></div>"
            f"<table>{''.join(trs)}</table></div></body></html>")


def diff_rows(old, new, context=1):
    """Wiersze nowego pliku z oznaczeniem dodanych/zmienionych linii, z pominieciem reszty."""
    a, b = old.splitlines(), new.splitlines()
    sm = difflib.SequenceMatcher(None, a, b)
    changed = set()
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal":
            changed.update(range(j1, j2))
    show = set()
    for j in changed:
        show.update(range(max(0, j - context), min(len(b), j + context + 1)))
    rows, prev = [], -1
    for j in sorted(show):
        if prev != -1 and j != prev + 1:
            rows.append(("gap", "", f"... (bez zmian: wiersze {prev + 2}–{j}) ..."))
        rows.append(("add" if j in changed else "ctx", j + 1, b[j]))
        prev = j
    return rows


# --------------------------------------------------------------------------------------
# FAZA 2 (Python z .venv): projekt Django, konfiguracja, przegladarka, zrzuty
# --------------------------------------------------------------------------------------
class Shooter:
    def __init__(self, state, lab, browser):
        self.state, self.lab, self.browser = state, lab, browser
        self.dir = lab / "zrzuty"
        self.dir.mkdir(exist_ok=True)
        self.render_page = browser.new_page(viewport={"width": 1240, "height": 400}, device_scale_factor=1.5)

    def _register(self, name, caption, section):
        shots = [s for s in self.state.get("shots", []) if s["name"] != name]
        shots.append({"name": name, "file": f"zrzuty/{name}.png", "caption": caption, "section": section})
        self.state["shots"] = shots

    def page(self, page, name, caption, section, full=False, el=None):
        page.wait_for_load_state("networkidle")
        path = self.dir / f"{name}.png"
        if el:
            page.locator(el).first.screenshot(path=str(path))
        else:
            page.screenshot(path=str(path), full_page=full)
        self._register(name, caption, section)
        log(f"zrzut: {path.name}")

    def html(self, content, name, caption, section):
        self.render_page.set_content(content)
        path = self.dir / f"{name}.png"
        self.render_page.locator("#w").screenshot(path=str(path))
        self._register(name, caption, section)
        log(f"zrzut: {path.name}")

    def terminal(self, group, name, caption, section, title="Windows PowerShell"):
        self.html(term_html(self.state["terminals"][group], title), name, caption, section)


def set_field(page, selector, value):
    """Ustawia wartosc pola (rowniez ukrytego przez select2/tinymce) i wyzwala 'change'."""
    page.eval_on_selector(selector, """(el, v) => {
        el.value = v; el.dispatchEvent(new Event('input', {bubbles:true}));
        el.dispatchEvent(new Event('change', {bubbles:true}));
        if (window.jQuery) { window.jQuery(el).trigger('change'); }
    }""", value)


def select_by_text(page, selector, text):
    val = page.eval_on_selector(selector, """(el, t) => {
        const o = Array.from(el.options).find(o => o.text.trim().includes(t)); return o ? o.value : null; }""", text)
    if val is None:
        raise SystemExit(f"Brak opcji '{text}' w {selector}")
    set_field(page, selector, val)


def click_nav(page, target):
    """Klikniecie, ktore wysyla formularz/przechodzi do nowej strony - czekamy na zaladowanie nowej strony."""
    loc = page.locator(target).first if isinstance(target, str) else target
    with page.expect_navigation():
        loc.click()
    page.wait_for_load_state("networkidle")


def open_tab(page, tab_id):
    page.locator(f"a.nav-link[href='{tab_id}']").first.click()
    page.wait_for_timeout(300)


def manage(state, group, display, py, project, args, check=True, keep=None):
    return run(state, group, display, [str(py), "manage.py"] + args, project, check=check, keep=keep)


def shell_json(py, project, code):
    out = subprocess.run([str(py), "manage.py", "shell", "-c", code], cwd=str(project), env=sub_env(),
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
    m = re.search(r"@@JSON@@(.*)@@END@@", out.stdout, re.S)
    if not m:
        raise SystemExit("Blad zapytania do bazy:\n" + out.stdout + out.stderr)
    return json.loads(m.group(1))


def phase_main(args):
    from playwright.sync_api import sync_playwright

    lab = args.lab_dir
    state = State(lab / "state.json")
    py = Path(sys.executable)
    project = lab / "mini-shop"
    base = f"http://127.0.0.1:{args.port}"
    admin_pw, cust_pw = state["admin_password"], state["customer_password"]

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(channel="msedge", headless=not args.headed)
        except Exception:
            try:
                browser = pw.chromium.launch(channel="chrome", headless=not args.headed)
            except Exception:
                subprocess.run([str(py), "-m", "playwright", "install", "chromium"], check=True)
                browser = pw.chromium.launch(headless=not args.headed)
        shot = Shooter(state, lab, browser)

        # --- Etap 1: terminal ---------------------------------------------------------
        shot.terminal("01_mkdir", "01_katalog", "Utworzenie katalogu roboczego django-oscar-lab", "etap1")
        shot.terminal("02_venv", "02_venv", "Utworzenie i aktywacja środowiska wirtualnego .venv", "etap1")
        shot.terminal("03_pip", "03_instalacja", "Aktualizacja pip i instalacja Django Oscar z obsługą miniaturek (sorl-thumbnail)", "etap1")
        shot.terminal("04_pipshow", "04_pip_show", "Sprawdzenie instalacji: python -m pip show django-oscar", "etap1")

        # --- Etap 2: projekt Django ----------------------------------------------------
        if not (project / "manage.py").exists():
            run(state, "05_project", "mkdir mini-shop", ["powershell", "-NoProfile", "-Command", "mkdir mini-shop"], lab)
            run(state, "05_project", "cd mini-shop", ["cmd", "/c", "rem"], project)
            run(state, "05_project", "django-admin startproject mini_shop .",
                [str(py.parent / "django-admin.exe"), "startproject", "mini_shop", "."], project)
            (lab / "settings_oryginal.py").write_text(
                (project / "mini_shop" / "settings.py").read_text(encoding="utf-8"), encoding="utf-8")
            (lab / "urls_oryginal.py").write_text(
                (project / "mini_shop" / "urls.py").read_text(encoding="utf-8"), encoding="utf-8")
            run(state, "06_tree", "Get-ChildItem -Force -Name",
                ["powershell", "-NoProfile", "-Command", "Get-ChildItem -Force -Name | Where-Object { $_ -in '.venv','mini-shop' }"], lab)
            run(state, "06_tree", "tree mini-shop /F /A",
                ["cmd", "/c", "tree", "mini-shop", "/F", "/A"], lab)
        shot.terminal("05_project", "05_startproject", "Utworzenie projektu Django mini_shop (django-admin startproject)", "etap2")
        shot.terminal("06_tree", "06_struktura", "Struktura katalogów projektu", "etap2")

        if not state.get("welcome_done"):
            page = browser.new_page(viewport={"width": 1366, "height": 800})
            with DevServer(py, project, args.port, lab / "server1.log") as srv:
                page.goto(base + "/")
                shot.page(page, "07_django_welcome", "Strona powitalna Django pod adresem http://127.0.0.1:8000/", "etap2")
                page.close()
            terms = state["terminals"]
            terms["07_runserver"] = [{"prompt": f"(.venv) PS {project}>", "cmd": "python manage.py runserver", "out": srv.output()}]
            state["terminals"] = terms
            state["welcome_done"] = True
        shot.terminal("07_runserver", "08_runserver", "Testowe uruchomienie serwera deweloperskiego Django (zatrzymanie: Ctrl+C)", "etap2")

        # --- Etap 3 i 4: konfiguracja --------------------------------------------------
        settings = project / "mini_shop" / "settings.py"
        s = settings.read_text(encoding="utf-8")
        if "from oscar.defaults import *" not in s:
            s = "from oscar.defaults import *\n" + s
            s = re.sub(r"INSTALLED_APPS = \[.*?\]", lambda m: INSTALLED_APPS, s, count=1, flags=re.S)
            s = re.sub(r"('context_processors': \[.*?)(\n\s*\],)", lambda m: m.group(1) + CONTEXT_PROCESSORS + m.group(2),
                       s, count=1, flags=re.S)
            s = re.sub(r"(MIDDLEWARE = \[.*?)(\n\])", lambda m: m.group(1) + MIDDLEWARE_ADD + m.group(2), s, count=1, flags=re.S)
            s = re.sub(r"DATABASES = \{.*?\n\}", lambda m: DATABASES, s, count=1, flags=re.S)
            s = re.sub(r"\nSTATIC_URL = .*\n", "\n", s, count=1)
            s = s.rstrip() + "\n" + SETTINGS_TAIL
            settings.write_text(s, encoding="utf-8")
            (project / "mini_shop" / "urls.py").write_text(URLS_PY, encoding="utf-8")
        orig = (lab / "settings_oryginal.py").read_text(encoding="utf-8")
        rows = diff_rows(orig, settings.read_text(encoding="utf-8"))
        # podzial na 3 obrazy o rozsadnej wysokosci
        chunks, cur = [], []
        for r in rows:
            cur.append(r)
            if len(cur) >= 48 and r[0] != "add":
                chunks.append(cur)
                cur = []
        if cur:
            chunks.append(cur)
        for i, ch in enumerate(chunks, 1):
            shot.html(code_html("mini_shop/settings.py", ch), f"09_settings_{i}",
                      f"Konfiguracja Oscara w mini_shop/settings.py (część {i}/{len(chunks)}, zmiany podświetlone)", "etap3")
        urows = [("add", i + 1, l) for i, l in enumerate(URLS_PY.splitlines())]
        shot.html(code_html("mini_shop/urls.py", urows), "10_urls", "Dołączenie URL-i Oscara w mini_shop/urls.py", "etap4")

        # --- Etap 5: migracje ----------------------------------------------------------
        if not state.get("migrated"):
            manage(state, "11_migrate", "python manage.py migrate", py, project, ["migrate"], keep=26)
            state["migrated"] = True
        shot.terminal("11_migrate", "11_migrate", "Wykonanie migracji bazy danych (python manage.py migrate)", "etap5")
        # Windows: Oscar nie moze utworzyc symlinku do obrazka "brak zdjecia" (wymaga uprawnien administratora),
        # wiec kopiujemy go do MEDIA_ROOT - dokladnie tak, jak podaje komunikat ImproperlyConfigured Oscara.
        if not state.get("media_fix"):
            run(state, "11b_media", "mkdir media -Force", ["powershell", "-NoProfile", "-Command", "mkdir media -Force"], project)
            run(state, "11b_media", "Copy-Item ..\\.venv\\Lib\\site-packages\\oscar\\static\\oscar\\img\\image_not_found.jpg media\\",
                ["powershell", "-NoProfile", "-Command",
                 "Copy-Item ..\\.venv\\Lib\\site-packages\\oscar\\static\\oscar\\img\\image_not_found.jpg media\\; Get-ChildItem media"],
                project)
            state["media_fix"] = True
        shot.terminal("11b_media", "11b_media_windows", "Skopiowanie obrazka image_not_found.jpg do MEDIA_ROOT (Windows nie pozwala Oscarowi utworzyć symlinku)", "etap5")

        if not state.get("oscar_home_done"):
            page = browser.new_page(viewport={"width": 1366, "height": 800})
            with DevServer(py, project, args.port, lab / "server2.log") as srv:
                page.goto(base + "/")
                shot.page(page, "12_oscar_pusty", "Działająca, pusta instalacja Oscara (strona główna sklepu)", "etap5")
                page.close()
            terms = state["terminals"]
            terms["12_runserver"] = [{"prompt": f"(.venv) PS {project}>", "cmd": "python manage.py runserver", "out": srv.output()}]
            state["terminals"] = terms
            state["oscar_home_done"] = True

        # --- Etap 6: superuser ---------------------------------------------------------
        if not state.get("superuser"):
            env = sub_env()
            env.update(DJANGO_SUPERUSER_USERNAME=ADMIN_USERNAME, DJANGO_SUPERUSER_EMAIL=ADMIN_EMAIL,
                       DJANGO_SUPERUSER_PASSWORD=admin_pw)
            terms = state["terminals"]
            terms["13_superuser"] = [
                {"prompt": f"(.venv) PS {project}>", "cmd": f'$env:DJANGO_SUPERUSER_USERNAME = "{ADMIN_USERNAME}"', "out": ""},
                {"prompt": f"(.venv) PS {project}>", "cmd": f'$env:DJANGO_SUPERUSER_EMAIL = "{ADMIN_EMAIL}"', "out": ""},
                {"prompt": f"(.venv) PS {project}>", "cmd": '$env:DJANGO_SUPERUSER_PASSWORD = "************"', "out": ""}]
            state["terminals"] = terms
            run(state, "13_superuser", "python manage.py createsuperuser --noinput",
                [str(py), "manage.py", "createsuperuser", "--noinput"], project, env=env)
            state["superuser"] = True
        shot.terminal("13_superuser", "13_createsuperuser", "Utworzenie użytkownika administracyjnego (createsuperuser)", "etap6")

        # --- Etap 7: kraje -------------------------------------------------------------
        if not state.get("countries"):
            manage(state, "14_countries", "python manage.py oscar_populate_countries", py, project,
                   ["oscar_populate_countries"])
            state["countries"] = True
        shot.terminal("14_countries", "14_populate_countries", "Załadowanie listy krajów (oscar_populate_countries)", "etap7")

        # kopia bazy przed czynnosciami w przegladarce - ponowne uruchomienie po bledzie zaczyna od tego punktu
        db, db_copy = project / "db.sqlite3", lab / "db_przed_dashboardem.sqlite3"
        if db_copy.exists():
            shutil.copy2(db_copy, db)
        else:
            shutil.copy2(db, db_copy)
        with DevServer(py, project, args.port, lab / "server3.log") as srv:
            admin_ctx = browser.new_context(viewport={"width": 1366, "height": 860})
            a = admin_ctx.new_page()
            # logowanie do dashboardu
            a.goto(base + "/dashboard/")
            a.fill("#id_username", ADMIN_EMAIL)
            a.fill("#id_password", admin_pw)
            shot.page(a, "15_logowanie", "Logowanie administratora do dashboardu Oscara (/dashboard/)", "etap6")
            click_nav(a, "form:has(#id_password) [type=submit]")
            a.wait_for_url(re.compile(r".*/dashboard/$"))
            shot.page(a, "16_dashboard", "Dashboard Oscara po zalogowaniu", "etap6")

            # Product Class: Laptop (+ atrybuty RAM i SSD dla wariantow)
            a.goto(base + "/dashboard/catalogue/product-type/create/")
            a.fill("#id_name", PRODUCT_CLASS)
            shot.page(a, "17_product_class_form", "Tworzenie klasy produktu (Product Class) Laptop", "etap7")
            open_tab(a, "#product_attributes")
            for i, (nm, code) in enumerate([("RAM", "ram"), ("SSD", "ssd")]):
                a.fill(f"#id_attributes-{i}-name", nm)
                a.fill(f"#id_attributes-{i}-code", code)
                a.select_option(f"#id_attributes-{i}-type", "text")
            shot.page(a, "17b_product_class_atrybuty", "Atrybuty klasy produktu Laptop: RAM i SSD (wykorzystane w wariantach)", "etap7")
            click_nav(a, a.locator("#create_update_product_class_form button[type=submit]").last)
            a.goto(base + "/dashboard/catalogue/product-types/")
            shot.page(a, "18_product_class_lista", "Lista klas produktów – utworzona klasa Laptop", "etap7")

            # Partner: TechShop
            a.goto(base + "/dashboard/partners/create/")
            a.fill("#id_name", PARTNER)
            click_nav(a, a.locator("form:has(#id_name) [type=submit]").first)
            a.goto(base + "/dashboard/partners/")
            shot.page(a, "19_partner", "Utworzony partner realizujący zamówienia (Fulfilment Partner) TechShop", "etap7")

            # Kategoria: Laptopy
            a.goto(base + "/dashboard/catalogue/categories/create/")
            a.fill("#id_name", CATEGORY)
            shot.page(a, "20_kategoria_form", "Tworzenie kategorii Laptopy w dashboardzie", "etap8")
            click_nav(a, "#create_update_category_form button[value=save]")
            a.goto(base + "/dashboard/catalogue/categories/")
            shot.page(a, "21_kategoria_lista", "Lista kategorii – utworzona kategoria Laptopy", "etap8")

            # Produkt: Laptop Lenovo ThinkBook
            a.goto(base + "/dashboard/catalogue/")
            a.select_option("#create_product_with_class_form select[name=product_class]", label=PRODUCT_CLASS)
            shot.page(a, "22_produkt_wybor_klasy", "Dodawanie produktu – wybór klasy produktu Laptop", "etap8")
            click_nav(a, a.locator("#create_product_with_class_form button[type=submit]"))
            a.fill("#id_title", PRODUCT["title"])
            shot.page(a, "23_produkt_dane", "Produkt Laptop Lenovo ThinkBook – zakładka danych produktu", "etap8")
            open_tab(a, "#product_category")
            select_by_text(a, "#id_productcategory_set-0-category", CATEGORY)
            shot.page(a, "24_produkt_kategoria", "Przypisanie produktu do kategorii Laptopy", "etap8")
            open_tab(a, "#product_stock")
            select_by_text(a, "#id_stockrecords-0-partner", PARTNER)
            a.fill("#id_stockrecords-0-partner_sku", PRODUCT["sku"])
            a.fill("#id_stockrecords-0-num_in_stock", PRODUCT["stock"])
            a.fill("#id_stockrecords-0-price_currency", "PLN")
            a.fill("#id_stockrecords-0-price", PRODUCT["price"])
            shot.page(a, "25_produkt_cena", "Rekord magazynowy (StockRecord): partner TechShop, cena 2999.00 PLN, 10 szt.", "etap8")
            click_nav(a, "#create_update_product_form button[value=save]")
            shot.page(a, "26_produkt_lista", "Lista produktów w dashboardzie po zapisaniu produktu", "etap8")

            # Produkt z wariantami: ThinkBook (rodzic) + 3 warianty
            a.goto(base + "/dashboard/catalogue/")
            a.select_option("#create_product_with_class_form select[name=product_class]", label=PRODUCT_CLASS)
            click_nav(a, a.locator("#create_product_with_class_form button[type=submit]"))
            a.fill("#id_title", PARENT_PRODUCT)
            open_tab(a, "#product_category")
            select_by_text(a, "#id_productcategory_set-0-category", CATEGORY)
            click_nav(a, "#create_update_product_form button[value=continue]")
            open_tab(a, "#child_products")
            shot.page(a, "27_rodzic_warianty", "Produkt nadrzędny ThinkBook – zakładka wariantów (Add variant)", "zad2")
            click_nav(a, "button[value=create-child]")
            for i, v in enumerate(VARIANTS):
                a.fill("#id_title", v["title"])
                open_tab(a, "#product_attributes")
                a.fill("#id_attr_ram", v["ram"])
                a.fill("#id_attr_ssd", v["ssd"])
                if i == 0:
                    shot.page(a, "28_wariant_atrybuty", "Wariant produktu – wartości atrybutów RAM i SSD", "zad2")
                open_tab(a, "#product_stock")
                select_by_text(a, "#id_stockrecords-0-partner", PARTNER)
                a.fill("#id_stockrecords-0-partner_sku", v["sku"])
                a.fill("#id_stockrecords-0-num_in_stock", v["stock"])
                a.fill("#id_stockrecords-0-price_currency", "PLN")
                a.fill("#id_stockrecords-0-price", v["price"])
                if i == 0:
                    shot.page(a, "29_wariant_cena", "Wariant produktu – własny rekord magazynowy i cena", "zad2")
                last = i == len(VARIANTS) - 1
                click_nav(a, "button[value=save]" if last else "button[value=create-another-child]")
            parent_id = shell_json(py, project,
                                   "import json;from oscar.apps.catalogue.models import Product;"
                                   f"print('@@JSON@@'+json.dumps(Product.objects.get(title='{PARENT_PRODUCT}').pk)+'@@END@@')")
            a.goto(base + f"/dashboard/catalogue/products/{parent_id}/")
            open_tab(a, "#child_products")
            shot.page(a, "30_rodzic_lista_wariantow", "Produkt ThinkBook z trzema wariantami (dashboard)", "zad2")
            a.goto(base + "/dashboard/catalogue/")
            shot.page(a, "31_produkty_wszystkie", "Lista produktów: produkt samodzielny, produkt nadrzędny i warianty", "zad2")

            # indeks Whoosh przebudowany po dodaniu wszystkich produktow, kategorii i stanow magazynowych
            terms = state["terminals"]
            terms.pop("31b_index", None)
            state["terminals"] = terms
            manage(state, "31b_index", "python manage.py rebuild_index --noinput", py, project,
                   ["rebuild_index", "--noinput"])
            shot.terminal("31b_index", "31b_rebuild_index", "Zbudowanie indeksu wyszukiwania Whoosh (rebuild_index)", "zad1")

            # --- Czesc publiczna: katalog ---------------------------------------------
            c_ctx = browser.new_context(viewport={"width": 1366, "height": 860})
            c = c_ctx.new_page()
            c.goto(base + "/")
            shot.page(c, "32_sklep_glowna", "Część publiczna sklepu – lista wszystkich produktów (All products)", "zad1", full=True)
            urls = shell_json(py, project, (
                "import json;from oscar.apps.catalogue.models import Product, Category;"
                f"print('@@JSON@@'+json.dumps([Category.objects.get(name='{CATEGORY}').get_absolute_url(),"
                f"Product.objects.get(title='{PRODUCT['title']}').get_absolute_url(),"
                f"Product.objects.get(title='{PARENT_PRODUCT}').get_absolute_url()])+'@@END@@')"))
            c.goto(base + urls[0])
            shot.page(c, "33_kategoria_publiczna", "Kategoria Laptopy w części publicznej sklepu – produkty w kategorii", "zad1", full=True)
            c.fill("input[name=q]", "Lenovo")
            click_nav(c, "form:has(input[name=q]) [type=submit]")
            shot.page(c, "33b_wyszukiwanie", "Wyszukanie produktu w sklepie (backend Whoosh)", "zad1")
            c.goto(base + urls[0])
            found = c.locator(f"article.product_pod a[title='{PRODUCT['title']}']")
            if found.count():
                click_nav(c, found.first)
            else:
                c.goto(base + urls[1])
            product_url = c.url
            shot.page(c, "34_produkt_strona", "Strona produktu: kategoria (breadcrumbs), nazwa, cena, dostępność i przycisk Add to cart", "zad1")
            c.goto(base + urls[2])
            shot.page(c, "35_produkt_warianty_publiczny", "Produkt nadrzędny ThinkBook w sklepie – lista wariantów", "zad2", full=True)

            # --- Zadanie 3: koszyk ------------------------------------------------------
            c.goto(product_url)
            click_nav(c, "#add_to_basket_form button[type=submit]")
            shot.page(c, "36_dodano_do_koszyka", "Komunikat po dodaniu produktu do koszyka", "zad3")
            c.goto(base + "/basket/")
            c.fill("#id_form-0-quantity", str(BASKET_QTY))
            shot.page(c, "37_koszyk_zmiana_ilosci", "Koszyk – zmiana liczby sztuk na 2", "zad3")
            # aktualizacja koszyka w Oscarze odbywa sie przez AJAX (bez przeladowania strony)
            with c.expect_response(lambda r: r.request.method == "POST" and "/basket/" in r.url):
                c.locator("#basket_formset button:has-text('Update')").first.click()
            c.wait_for_load_state("networkidle")
            c.goto(base + "/basket/")
            shot.page(c, "38_koszyk_wartosc", "Koszyk po aktualizacji ilości – wartość koszyka", "zad3", full=True)

            # --- Zadanie 4: checkout ----------------------------------------------------
            click_nav(c, c.locator("a:has-text('Proceed to checkout')").first)
            shot.page(c, "39_checkout_identyfikacja", "Checkout, krok 1 – identyfikacja klienta (logowanie lub rejestracja)", "zad4")
            if c.locator("#id_username").count():  # bramka checkoutu (gdy wlaczony OSCAR_ALLOW_ANON_CHECKOUT)
                c.fill("#id_username", CUSTOMER["email"])
                c.check("input[name=options][value=new]")
                click_nav(c, c.locator("form:has(#id_username) button[type=submit]").first)
            c.fill("#id_registration-email", CUSTOMER["email"])
            c.fill("#id_registration-password1", cust_pw)
            c.fill("#id_registration-password2", cust_pw)
            shot.page(c, "40_checkout_rejestracja", "Checkout – rejestracja nowego klienta", "zad4")
            click_nav(c, "button[name=registration_submit]")
            if "/checkout/shipping-address/" not in c.url:
                c.goto(base + "/checkout/shipping-address/")
            c.fill("#id_first_name", CUSTOMER["first_name"])
            c.fill("#id_last_name", CUSTOMER["last_name"])
            c.fill("#id_line1", CUSTOMER["line1"])
            c.fill("#id_line4", CUSTOMER["city"])
            c.fill("#id_postcode", CUSTOMER["postcode"])
            c.select_option("#id_country", "PL")
            if c.locator("#id_phone_number").count():
                c.fill("#id_phone_number", CUSTOMER["phone"])
            shot.page(c, "41_checkout_adres", "Checkout, krok 2 – adres dostawy", "zad4", full=True)
            click_nav(c, c.locator("#new_shipping_address button[type=submit]").first)
            if "/checkout/shipping-method/" in c.url:
                shot.page(c, "42_checkout_dostawa", "Checkout, krok 3 – sposób dostawy", "zad4", full=True)
                click_nav(c, c.locator("main form button[type=submit], #content_inner form button[type=submit]").first)
            if "/checkout/payment-method/" in c.url:
                c.wait_for_load_state()
            if "/checkout/payment-details/" in c.url:
                shot.page(c, "43_checkout_platnosc", "Checkout, krok 4 – płatność (domyślnie bez bramki płatniczej)", "zad4", full=True)
                click_nav(c, "#view_preview")
            shot.page(c, "44_checkout_podsumowanie", "Checkout, krok 5 – podsumowanie zamówienia (Preview)", "zad4", full=True)
            click_nav(c, "#place-order")
            shot.page(c, "45_checkout_potwierdzenie", "Checkout, krok 6 – utworzenie zamówienia (potwierdzenie)", "zad4", full=True)

            # --- Zadanie 5: zamowienie w dashboardzie ----------------------------------
            order = shell_json(py, project, """
import json
from oscar.apps.order.models import Order
o = Order.objects.order_by('-id').first()
d = {'number': o.number, 'status': o.status, 'email': o.email,
     'customer': (o.user.get_full_name() if o.user else '') or (o.shipping_address.name if o.shipping_address else o.email),
     'total_incl_tax': str(o.total_incl_tax), 'total_excl_tax': str(o.total_excl_tax),
     'shipping': str(o.shipping_incl_tax), 'shipping_method': o.shipping_method,
     'currency': o.currency, 'date': o.date_placed.strftime('%Y-%m-%d %H:%M'),
     'address': str(o.shipping_address) if o.shipping_address else '',
     'lines': [{'title': l.title, 'qty': l.quantity, 'unit': str(l.unit_price_incl_tax),
                'total': str(l.line_price_incl_tax), 'partner': l.partner_name, 'sku': l.partner_sku,
                'status': l.status} for l in o.lines.all()]}
print('@@JSON@@' + json.dumps(d) + '@@END@@')
""")
            state["order"] = order
            a.goto(base + "/dashboard/orders/")
            shot.page(a, "46_zamowienia_lista", "Dashboard – lista zamówień z utworzonym zamówieniem", "zad5")
            a.goto(base + f"/dashboard/orders/{order['number']}/")
            shot.page(a, "47_zamowienie_szczegoly", "Dashboard – szczegóły zamówienia (klient, pozycje, ilości, ceny, status)", "zad5", full=True)
            c.goto(base + "/basket/")
            shot.page(c, "48_koszyk_po_zamowieniu", "Koszyk klienta po złożeniu zamówienia (nowy, pusty koszyk)", "zad5")
            admin_ctx.close()
            c_ctx.close()
        state["shots"] = [s for s in state["shots"] if s["name"] != "49_runserver_log"]
        state["oscar_version"] = shell_json(py, project, "import json,oscar,django;print('@@JSON@@'+json.dumps([oscar.get_version(), django.get_version()])+'@@END@@')")
        state["finished"] = dt.datetime.now().isoformat(timespec="minutes")
        browser.close()

    build_report(args, state)


# --------------------------------------------------------------------------------------
# FAZA 3: sprawozdanie (bez zmiany tabel i stylow szablonu)
# --------------------------------------------------------------------------------------
def esc(t):
    return html.escape(t, quote=False)


P_BOLD = ('<w:p><w:pPr><w:tabs><w:tab w:val="num" w:pos="1400"/></w:tabs><w:ind w:left="300"/>'
          '<w:rPr><w:rFonts w:ascii="Cambria" w:hAnsi="Cambria"/><w:b/><w:lang w:eastAsia="pl-PL"/></w:rPr></w:pPr>'
          '<w:r><w:rPr><w:rFonts w:ascii="Cambria" w:hAnsi="Cambria"/><w:b/><w:lang w:eastAsia="pl-PL"/></w:rPr>'
          '<w:t xml:space="preserve">{}</w:t></w:r></w:p>')
P_TEXT = ('<w:p><w:pPr><w:tabs><w:tab w:val="num" w:pos="1400"/></w:tabs><w:ind w:left="300"/></w:pPr>'
          '<w:r><w:t xml:space="preserve">{}</w:t></w:r></w:p>')
P_EMPTY = '<w:p><w:pPr><w:tabs><w:tab w:val="num" w:pos="1400"/></w:tabs><w:ind w:left="300"/></w:pPr></w:p>'


def p_bold(t):
    return P_BOLD.format(esc(t))


def p_text(t):
    return P_TEXT.format(esc(t))


def p_image(rid, pic_id, name, cx, cy):
    return ('<w:p><w:pPr><w:tabs><w:tab w:val="num" w:pos="1400"/></w:tabs><w:ind w:left="300"/></w:pPr><w:r><w:drawing>'
            f'<wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
            '<wp:effectExtent l="0" t="0" r="0" b="0"/>'
            f'<wp:docPr id="{pic_id}" name="Obraz {pic_id}" descr="{esc(name)}"/>'
            '<wp:cNvGraphicFramePr><a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/></wp:cNvGraphicFramePr>'
            '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
            '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            f'<pic:nvPicPr><pic:cNvPr id="{pic_id}" name="{esc(name)}"/><pic:cNvPicPr/></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic>'
            '</wp:inline></w:drawing></w:r></w:p>')


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def mapping_table(tbl_pr, rows, widths=None):
    """Nowa tabela (Zadanie 6) z wlasciwosciami skopiowanymi z tabeli punktacji szablonu."""
    widths = widths or [2600, 3400, 3089]
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
    tbl_pr = re.sub(r'<w:tblW [^>]*/>', f'<w:tblW w:w="{sum(widths)}" w:type="dxa"/>', tbl_pr)

    def cell(text, w, style):
        return (f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/></w:tcPr>'
                f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr><w:r><w:t xml:space="preserve">{esc(text)}</w:t></w:r></w:p></w:tc>')
    out = [f"<w:tbl>{tbl_pr}<w:tblGrid>{grid}</w:tblGrid>"]
    for i, r in enumerate(rows):
        style = "TableHeading" if i == 0 else "TableText"
        out.append("<w:tr>" + "".join(cell(t, w, style) for t, w in zip(r, widths)) + "</w:tr>")
    out.append("</w:tbl>")
    return "".join(out)


def report_content(state):
    o = state.get("order") or {}
    ov = state.get("oscar_version") or ["?", "?"]
    cur = o.get("currency", "PLN")
    shots = {s["name"]: s for s in state["shots"]}
    lines_txt = "; ".join(f"{l['title']} – {l['qty']} szt. × {l['unit']} {cur} = {l['total']} {cur} (partner {l['partner']}, SKU {l['sku']})"
                          for l in o.get("lines", []))
    C = []  # ("b", tekst) | ("t", tekst) | ("img", nazwa) | ("table", wiersze) | ("e",)

    def imgs(*names):
        for n in names:
            if n in shots:
                C.append(("img", n))

    def imgs_prefix(prefix):
        for n in sorted(shots):
            if n.startswith(prefix):
                C.append(("img", n))

    C += [("t", "Laboratorium wykonano lokalnie w systemie Windows 11 (PowerShell, Python, virtualenv), bez Dockera i bez Oscar Sandbox. "
                f"Wykorzystano Django Oscar {ov[0]} oraz Django {ov[1]} z bazą SQLite. Wszystkie kroki instrukcji wykonano skryptem "
                "lab1_oscar_auto.py, który po każdym etapie zapisał zrzut ekranu (okno terminala z rzeczywistym wynikiem polecenia "
                "lub widok przeglądarki)."),
          ("e",),
          ("b", "1. Etap 1 – katalog roboczy, środowisko wirtualne i instalacja Django Oscar"),
          ("t", "Utworzono katalog roboczy django-oscar-lab oraz środowisko wirtualne poleceniem py -m venv .venv i aktywowano je "
                "skryptem .venv\\Scripts\\Activate.ps1 (w wierszu poleceń pojawia się prefiks (.venv)). Następnie zaktualizowano pip "
                "i zainstalowano pakiet django-oscar[sorl-thumbnail] oraz silnik wyszukiwania Whoosh (pakiet whoosh, wyjaśnienie w punkcie 3); "
                "instalację potwierdzono poleceniem python -m pip show django-oscar.")]
    imgs("01_katalog", "02_venv", "03_instalacja", "04_pip_show")
    C += [("t", "Pytanie kontrolne – dlaczego .venv, a nie instalacja globalna? Środowisko wirtualne izoluje zależności projektu "
                "(konkretne wersje Django, Oscara, haystack, treebeard, sorl-thumbnail) od globalnej instalacji Pythona. Różne projekty "
                "mogą używać różnych wersji bibliotek bez konfliktów, instalacja nie wymaga uprawnień administratora, a środowisko "
                "można łatwo odtworzyć lub usunąć bez wpływu na system."),
          ("e",),
          ("b", "2. Etap 2 – utworzenie projektu Django"),
          ("t", "W katalogu mini-shop utworzono projekt poleceniem django-admin startproject mini_shop . – końcowa kropka powoduje "
                "utworzenie plików w bieżącym katalogu. Plik manage.py służy do poleceń administracyjnych, a pakiet mini_shop zawiera "
                "ustawienia (settings.py) i konfigurację URL-i (urls.py); .venv pozostaje w katalogu głównym obok projektu. "
                "Testowe uruchomienie serwera (python manage.py runserver) wyświetliło stronę powitalną Django.")]
    imgs("05_startproject", "06_struktura", "07_django_welcome", "08_runserver")
    C += [("e",),
          ("b", "3. Etap 3 i 4 – konfiguracja Oscara i URL-e"),
          ("t", "W pliku settings.py dodano from oscar.defaults import *, zastąpiono listę INSTALLED_APPS aplikacjami Oscara i jego "
                "zależnościami (widget_tweaks, haystack, treebeard, sorl.thumbnail, django_tables2), ustawiono SITE_ID = 1, dodano "
                "context processors, BasketMiddleware i FlatpageFallbackMiddleware, AUTHENTICATION_BACKENDS (logowanie adresem e-mail), "
                "bazę SQLite z ATOMIC_REQUESTS, ustawienia plików statycznych i mediów oraz pipeline statusów zamówienia "
                "(Pending → Being processed → Processed / Cancelled). Dodatkowo ustawiono OSCAR_DEFAULT_CURRENCY = 'PLN', aby ceny "
                "były wyrażone w złotych. W urls.py dołączono wszystkie URL-e Oscara jednym wpisem apps.get_app_config('oscar').urls[0]."),
          ("t", "Zmiana względem instrukcji – wyszukiwanie: zamiast prostego backendu Haystack (SimpleEngine) użyto backendu Whoosh "
                "(WhooshEngine z indeksem w katalogu whoosh_index) oraz HAYSTACK_SIGNAL_PROCESSOR = RealtimeSignalProcessor. "
                "Oscar 4 wyświetla listy produktów (All products, strony kategorii) przez Haystack z filtrami is_public i structure, "
                "których SimpleEngine nie obsługuje – z nim katalog pokazywał 0 wyników, mimo że produkty istniały. Whoosh to lokalny "
                "indeks w plikach, niewymagający dodatkowego serwera.")]
    imgs_prefix("09_settings_")
    imgs("10_urls")
    C += [("e",),
          ("b", "4. Etap 5 i 6 – migracje i użytkownik administracyjny"),
          ("t", "Polecenie python manage.py migrate utworzyło tabele wszystkich aplikacji Django i Oscara. W systemie Windows Oscar "
                "nie może sam utworzyć dowiązania symbolicznego do obrazka „brak zdjęcia” (wymaga to uprawnień administratora), "
                "dlatego – zgodnie z komunikatem Oscara – skopiowano plik image_not_found.jpg do katalogu media. Po uruchomieniu "
                "serwera pod adresem http://127.0.0.1:8000/ widoczna jest działająca, ale pusta instalacja sklepu. Następnie "
                f"utworzono superusera ({ADMIN_EMAIL}) i zalogowano się do dashboardu /dashboard/.")]
    imgs("11_migrate", "11b_media_windows", "12_oscar_pusty", "13_createsuperuser", "15_logowanie", "16_dashboard")
    C += [("e",),
          ("b", "5. Etap 7 i 8 – klasa produktu, partner, kategoria i produkt"),
          ("t", "Poleceniem python manage.py oscar_populate_countries załadowano listę krajów (potrzebną m.in. w adresie dostawy; "
                "polecenie wymaga pakietu pycountry, który doinstalowano). W dashboardzie utworzono klasę produktu Laptop "
                "(z atrybutami RAM i SSD wykorzystanymi w zadaniu 2), partnera TechShop, kategorię Laptopy oraz produkt "
                f"Laptop Lenovo ThinkBook z ceną {PRODUCT['price']} PLN i dostępnością {PRODUCT['stock']} szt.")]
    imgs("14_populate_countries", "17_product_class_form", "17b_product_class_atrybuty", "18_product_class_lista", "19_partner",
         "20_kategoria_form", "21_kategoria_lista", "22_produkt_wybor_klasy", "23_produkt_dane", "24_produkt_kategoria",
         "25_produkt_cena", "26_produkt_lista")
    C += [("e",),
          ("b", "6. Zadanie 1 – katalog"),
          ("t", "Po dodaniu produktów zbudowano indeks wyszukiwania poleceniem python manage.py rebuild_index. W części publicznej "
                "sklepu lista All products zawiera produkt Laptop Lenovo ThinkBook oraz produkt nadrzędny ThinkBook (warianty nie są "
                "pokazywane osobno), a strona kategorii Laptopy pokazuje produkty tej kategorii. Produkt można też znaleźć wyszukiwarką.")]
    imgs("31b_rebuild_index", "32_sklep_glowna", "33_kategoria_publiczna", "33b_wyszukiwanie", "34_produkt_strona")
    C += [("t", "1. Kategorię widzimy w menu kategorii (Browse store oraz panel „Show results for”), na stronie kategorii "
                "/catalogue/category/laptopy_…/ oraz w okruszkach (breadcrumbs) na stronie produktu: Home / Laptopy / produkt."),
          ("t", "2. Nazwa produktu (pole Product.title) jest widoczna w wynikach wyszukiwania i na liście produktów oraz jako nagłówek "
                "strony szczegółów produktu."),
          ("t", "3. Cena nie jest polem produktu – jest przechowywana w rekordzie magazynowym StockRecord (pola price i price_currency), "
                "który łączy produkt z partnerem (aplikacja partner)."),
          ("t", "4. Dostępność również wynika z rekordu StockRecord (num_in_stock, num_allocated); komunikat „In stock (10 available)” "
                "wylicza strategia partnera (Strategy i jej polityka dostępności)."),
          ("t", "5. Oscar oddziela produkt (CO sprzedajemy – katalog) od oferty sprzedaży partnera (KTO sprzedaje, za ile i ile ma na stanie). "
                "Ten sam produkt może być sprzedawany przez wielu partnerów lub z wielu magazynów, z różnymi cenami, walutami i stanami, "
                "a wybór oferty realizuje strategia. Dzięki temu katalog pozostaje niezależny od logistyki i polityki cenowej."),
          ("e",),
          ("b", "7. Zadanie 2 – wariant produktu"),
          ("t", "Utworzono produkt nadrzędny ThinkBook (struktura parent) i trzy warianty (struktura child): 16 GB / 512 GB, "
                "16 GB / 1 TB oraz 32 GB / 1 TB. Wartości RAM i SSD są atrybutami klasy produktu Laptop, a każdy wariant ma własny "
                "StockRecord z ceną i stanem magazynowym.")]
    imgs("27_rodzic_warianty", "28_wariant_atrybuty", "29_wariant_cena", "30_rodzic_lista_wariantow", "31_produkty_wszystkie",
         "35_produkt_warianty_publiczny")
    C += [("t", "1. Tak – każdy wariant jest osobnym rekordem Product (structure = child) z własnym identyfikatorem, SKU, ceną i stanem, "
                "ale nie jest samodzielnym produktem w katalogu – należy do produktu nadrzędnego."),
          ("t", "2. Wspólne dla produktu (rodzica) są: nazwa ogólna, opis, klasa produktu, kategorie, zdjęcia i rekomendacje."),
          ("t", "3. Do konkretnego wariantu należą: wartości atrybutów (RAM, SSD), własny tytuł/UPC oraz rekord magazynowy – SKU partnera, "
                "cena i liczba sztuk. To wariant trafia do koszyka i do zamówienia."),
          ("t", "4. Po dodaniu koloru wystarczy dodać do klasy produktu Laptop nowy atrybut (np. kolor typu option z grupą opcji "
                "czarny/srebrny) i utworzyć warianty dla kombinacji RAM × SSD × kolor. Schemat bazy się nie zmienia – Oscar "
                "przechowuje atrybuty w modelu EAV (ProductAttribute / ProductAttributeValue)."),
          ("e",),
          ("b", "8. Zadanie 3 – koszyk")]
    imgs("36_dodano_do_koszyka", "37_koszyk_zmiana_ilosci", "38_koszyk_wartosc")
    C += [("t", f"Jako klient otwarto produkt, dodano go do koszyka, zmieniono liczbę sztuk na {BASKET_QTY} i sprawdzono wartość "
                f"koszyka ({BASKET_QTY} × {PRODUCT['price']} PLN)."),
          ("t", "Czy w tym momencie istnieje już zamówienie? Nie. Koszyk (Basket, aplikacja basket) to tymczasowy, edytowalny zbiór "
                "pozycji powiązany z sesją lub użytkownikiem – można go zmieniać, porzucić lub scalić. Nie ma jeszcze danych klienta, "
                "adresu, sposobu dostawy ani płatności, nie ma numeru zamówienia, a towar nie jest zarezerwowany. Zamówienie (Order, "
                "aplikacja order) powstaje dopiero na końcu procesu checkout jako trwały, niezmienny zapis transakcji."),
          ("e",),
          ("b", "9. Zadanie 4 – checkout")]
    imgs("39_checkout_identyfikacja", "40_checkout_rejestracja", "41_checkout_adres", "42_checkout_dostawa",
         "43_checkout_platnosc", "44_checkout_podsumowanie", "45_checkout_potwierdzenie")
    C += [("t", "Kolejne kroki: 1) identyfikacja klienta – logowanie lub rejestracja (zarejestrowano klienta "
                f"{CUSTOMER['email']}), 2) adres dostawy, 3) sposób dostawy – przy jednej dostępnej metodzie (Free shipping) Oscar "
                "wybiera ją automatycznie i pomija ten ekran, 4) płatność – domyślny widok bez bramki płatniczej, 5) podsumowanie "
                "(Preview), 6) złożenie zamówienia (Place order) i strona potwierdzenia z numerem zamówienia."),
          ("t", "Aby koszyk mógł stać się zamówieniem, potrzebne są: niepusty koszyk z dostępnymi produktami (ceny ze StockRecord), "
                "dane klienta (konto lub e-mail gościa), adres dostawy (z krajem), wybrana metoda dostawy i jej koszt, dane płatności "
                "(źródło płatności, adres rozliczeniowy) oraz wyliczone sumy (pozycje, dostawa, rabaty, podatki). Przy składaniu "
                "zamówienia Oscar nadaje numer, zapisuje Order, OrderLine, adresy i statusy oraz alokuje stan magazynowy."),
          ("e",),
          ("b", "10. Zadanie 5 – zamówienie")]
    imgs("46_zamowienia_lista", "47_zamowienie_szczegoly", "48_koszyk_po_zamowieniu")
    if o:
        C += [("t", f"Numer zamówienia: {o['number']}"),
              ("t", f"Status zamówienia: {o['status']}"),
              ("t", f"Klient: {o['customer']}, e-mail {o['email']} (konto zarejestrowane w kroku identyfikacji; imię i nazwisko z adresu dostawy)"),
              ("t", f"Pozycje, ilości i ceny: {lines_txt}"),
              ("t", f"Dostawa: {o['shipping_method']} ({o['shipping']} {cur}); łączna wartość zamówienia: {o['total_incl_tax']} {cur}"),
              ("t", "Porównanie z koszykiem: pozycje, ilości i ceny są takie same jak w koszyku, ale zamówienie jest trwałym zapisem – "
                    "ma numer, status, klienta, adres i metodę dostawy oraz datę złożenia. Ceny pozycji są w zamówieniu skopiowane, więc "
                    "późniejsza zmiana ceny produktu nie zmieni zamówienia. Po złożeniu zamówienia koszyk został zamknięty (status "
                    "Submitted), a klient otrzymał nowy, pusty koszyk.")]
    C += [("e",),
          ("b", "11. Zadanie 6 – mapowanie na aplikacje Oscara"),
          ("table", [["Czynność użytkownika", "Element domeny", "Aplikacja Oscara"],
                     ["Oglądanie produktu", "Produkt, kategoria, klasa produktu; cena i dostępność (StockRecord)", "catalogue (+ partner)"],
                     ["Dodanie do koszyka", "Koszyk (Basket), pozycja koszyka (Line)", "basket"],
                     ["Zmiana ilości", "Pozycja koszyka – ilość (quantity)", "basket"],
                     ["Checkout", "Proces zamówienia: klient, adres, dostawa, płatność", "checkout (+ address, shipping, payment)"],
                     ["Utworzenie zamówienia", "Zamówienie (Order), pozycje zamówienia, status", "order"],
                     ["Obsługa klienta", "Konto klienta, historia zamówień, adresy", "customer"],
                     ["Promocja", "Oferta / rabat (ConditionalOffer), voucher", "offer (+ voucher)"],
                     ["Wysyłka", "Metoda dostawy i jej koszt", "shipping"]]),
          ("e",),
          ("b", "12. Zadanie końcowe – co właściwie dostaliśmy od Oscara?"),
          ("t", "Django jest frameworkiem webowym, który daje podstawy aplikacji: ORM i migracje, routing URL-i, szablony, formularze, "
                "uwierzytelnianie, sesje i panel administracyjny. Django Oscar to framework zbudowany na Django, który dostarcza gotową "
                "domenę e-commerce – przemyślany model danych katalogu (Product, ProductClass, Category, atrybuty i warianty), partnerów "
                "ze StockRecord, koszyk, proces checkout oraz zamówienie ze statusami. Samodzielne pisanie modeli Product, Basket, Order "
                "i Checkout oznaczałoby powtarzanie sprawdzonych rozwiązań i ryzyko błędów, np. przy zamrażaniu cen w zamówieniu, "
                "alokacji stanu magazynowego czy scalaniu koszyków. Oscar dostarcza też dashboard do zarządzania katalogiem "
                "i zamówieniami, a jego aplikacje można nadpisywać (fork) bez modyfikowania kodu frameworka. Projekt nadal jest naszym "
                "projektem Django – Oscar to zestaw aplikacji dołączonych w INSTALLED_APPS i urls.py, więc możemy skupić się na logice "
                "biznesowej sklepu zamiast budować od zera katalog, koszyk, checkout i zamówienie."),
          ("e",),
          ("b", "13. Pytanie kontrolne – Basket ≠ Order"),
          ("t", "Nie. Jeśli klient dodał laptopa do koszyka, ale nie przeszedł checkoutu i nie zapłacił, produkt nie jest sprzedany. "
                "Koszyk wyraża jedynie zamiar zakupu: jest tymczasowy, może zostać porzucony lub zmieniony, nie ma danych dostawy "
                "i płatności, a stan magazynowy nie jest alokowany. Sprzedaż zaczyna się dopiero od utworzenia zamówienia (Order) "
                "w procesie checkout – wtedy Oscar zapisuje transakcję, alokuje towar i nadaje status (Pending), a kolejne etapy "
                "obejmują płatność i realizację."),
          ]
    conclusions = [
        "Projekt Django z Django Oscar uruchomiono lokalnie w środowisku wirtualnym z bazą SQLite; konfiguracja Oscara polega na "
        "dodaniu jego aplikacji, context processors, middleware, backendu uwierzytelniania i URL-i, a migracje tworzą kompletny model "
        "danych sklepu.",
        "Katalogiem zarządza się przez dashboard Oscara: klasa produktu definiuje atrybuty, partner reprezentuje sprzedawcę/magazyn, "
        "a cena i dostępność są przechowywane w StockRecord, a nie w samym produkcie.",
        "Warianty to produkty podrzędne (child) produktu nadrzędnego – współdzielą opis i kategorie, ale mają własne atrybuty, cenę "
        "i stan magazynowy.",
        "Koszyk nie jest zamówieniem: zamówienie powstaje dopiero po przejściu checkoutu (klient, adres, dostawa, płatność, "
        "podsumowanie) i jest trwałym zapisem widocznym w dashboardzie ze statusem Pending.",
        "Listy produktów w katalogu Oscara korzystają z wyszukiwarki (Haystack): prosty backend SimpleEngine nie obsługuje ich filtrów, "
        "dlatego użyto backendu Whoosh i po dodaniu produktów zbudowano indeks (rebuild_index).",
        "Django daje fundament aplikacji webowej, a Oscar – gotową, rozszerzalną domenę e-commerce podzieloną na aplikacje "
        "(catalogue, partner, basket, checkout, order, customer, offer, shipping, payment).",
    ]
    return C, conclusions


def build_report(args, state, content_fn=None):
    template = Path(args.template)
    if not template.exists():
        log(f"Brak szablonu {template} - pomijam generowanie sprawozdania.")
        return
    lab = args.lab_dir
    content, conclusions = (content_fn or report_content)(state)
    shots = {s["name"]: s for s in state["shots"]}
    with zipfile.ZipFile(template) as z:
        entries = [(i, z.read(i.filename)) for i in z.infolist()]
    files = {i.filename: d for i, d in entries}
    doc = files["word/document.xml"].decode("utf-8")
    rels = files["word/_rels/document.xml.rels"].decode("utf-8")

    # paragrafy szablonu w sekcji "Opis cwiczenia / Opracowanie wynikow"
    paras = [(m.start(), m.end(), m.group(0)) for m in re.finditer(r"<w:p [^>]*>(?:(?!<w:p[ >]).)*?</w:p>", doc, re.S)]

    def ptext(x):
        return "".join(re.findall(r"<w:t(?: [^>]*)?>([^<]*)</w:t>", x))

    idx = {ptext(p[2]).strip(): k for k, p in enumerate(paras)}
    k_np = idx.get("Np.:")
    k_zest = idx.get("Zestawienie wyników")
    k_wn = idx.get("Wnioski:")
    if None in (k_np, k_zest, k_wn):
        raise SystemExit("Nie rozpoznano struktury szablonu (Np.: / Zestawienie wyników / Wnioski:).")

    tbl_pr = re.search(r"Rubryka przykładowej punktacji.*?<w:tbl>(<w:tblPr>.*?</w:tblPr>)", doc, re.S).group(1)
    max_w_emu = int((11906 - 1700 - 1106 - 300) / 1440 * 914400)  # szerokosc tekstu minus wciecie
    max_h_emu = int(8.4 * 914400)
    rid_n = 1000
    pic_n = 1000
    media = {}
    fig = 0
    xml = []
    for item in content:
        kind = item[0]
        if kind == "b":
            xml.append(p_bold(item[1]))
        elif kind == "t":
            xml.append(p_text(item[1]))
        elif kind == "e":
            xml.append(P_EMPTY)
        elif kind == "table":
            xml.append(mapping_table(tbl_pr, item[1], item[2] if len(item) > 2 else None))
            xml.append(P_EMPTY)
        elif kind == "img":
            s = shots[item[1]]
            src = lab / s["file"]
            if not src.exists():
                continue
            fig += 1
            rid_n += 1
            pic_n += 1
            rid = f"rIdLab{rid_n}"
            target = f"media/lab1_{item[1]}.png"
            media[f"word/{target}"] = src.read_bytes()
            rels = rels.replace("</Relationships>",
                                f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="{target}"/></Relationships>')
            w, h = png_size(src)
            cx = max_w_emu
            cy = int(cx * h / w)
            if cy > max_h_emu:
                cy = max_h_emu
                cx = int(cy * w / h)
            xml.append(p_image(rid, pic_n, s["file"], cx, cy))
            xml.append(p_text(f"Rys. {fig}. {s['caption']}"))
    start = paras[k_np][0]
    end = paras[k_zest][1]
    doc = doc[:start] + "".join(xml) + doc[end:]
    # wnioski - w miejsce pustego akapitu za "Wnioski:"
    paras = [(m.start(), m.end(), m.group(0)) for m in re.finditer(r"<w:p [^>]*>(?:(?!<w:p[ >]).)*?</w:p>", doc, re.S)]
    k_wn = next(k for k, p in enumerate(paras) if ptext(p[2]).strip() == "Wnioski:")
    after = paras[k_wn + 1]
    concl = "".join(p_text(f"{i}. {t}") for i, t in enumerate(conclusions, 1))
    if ptext(after[2]).strip() == "":
        doc = doc[:after[0]] + concl + doc[after[1]:]
    else:
        doc = doc[:paras[k_wn][1]] + concl + doc[paras[k_wn][1]:]
    # przestrzenie nazw wp/r sa juz zadeklarowane w szablonie
    files["word/document.xml"] = doc.encode("utf-8")
    files["word/_rels/document.xml.rels"] = rels.encode("utf-8")
    out = Path(args.output)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for info, _ in entries:
            z.writestr(info, files[info.filename])
        for name, data in media.items():
            z.writestr(name, data)
    log(f"Sprawozdanie zapisane: {out}  (rysunkow: {fig})")


# --------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="LAB1 Django Oscar - automatyzacja + zrzuty + sprawozdanie")
    ap.add_argument("--lab-dir", type=Path, default=SCRIPT_DIR / "django-oscar-lab")
    ap.add_argument("--template", type=Path,
                    default=Path.home() / "Downloads" / "Załącznik_2_Szablon_sprawozdania (1).docx")
    ap.add_argument("--output", type=Path, default=SCRIPT_DIR / "Sprawozdanie_LAB1_Django_Oscar.docx")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--oscar-version", default="")
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--phase", default="setup", choices=["setup", "main"])
    args = ap.parse_args()
    args.lab_dir = args.lab_dir.resolve()
    if args.report_only:
        build_report(args, State(args.lab_dir / "state.json"))
    elif args.phase == "setup":
        phase_setup(args)
    else:
        phase_main(args)


if __name__ == "__main__":
    main()
