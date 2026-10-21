# -*- coding: utf-8 -*-
"""Zadanie 1: moduly Oscara - modele, rozmiar kodu i zaleznosci miedzy aplikacjami (analiza kodu oscar.apps)."""
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
import re  # noqa: E402
from collections import Counter  # noqa: E402

import oscar  # noqa: E402
from django.apps import apps  # noqa: E402
from django.conf import settings  # noqa: E402

APPS = ["catalogue", "basket", "checkout", "order", "customer", "offer", "shipping", "payment", "partner"]
ROOT = Path(oscar.__file__).resolve().parent / "apps"
LABELS = {p.name for p in ROOT.iterdir() if p.is_dir() and not p.name.startswith("_")}
DEP_RE = re.compile(r"""get_(?:model|class|classes)\(\s*["']([a-z_]+)|from oscar\.apps\.([a-z_]+)""")


def analyse(app):
    files = [p for p in (ROOT / app).rglob("*.py") if "migrations" not in p.parts]
    deps = Counter()
    lines = 0
    for p in files:
        text = p.read_text(encoding="utf-8")
        lines += text.count("\n")
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

print("Aplikacje Oscara wykorzystywane w mini_shop (pakiet oscar.apps):\n")
print(f"{'moduł':<10} {'modele':>6} {'pliki':>6} {'linie':>6}  zależy od (liczba odwołań get_model/get_class/import w kodzie)")
for r in rows:
    deps = ", ".join(f"{a}({n})" for a, n in r["deps"][:6])
    print(f"{r['app']:<10} {len(r['models']):>6} {r['files']:>6} {r['lines']:>6}  {deps}")
print("\nModele (tabele) poszczególnych modułów:")
for r in rows:
    print(f"  {r['app']:<10} {', '.join(r['models']) or '(brak własnych modeli - steruje procesem, korzysta z innych modułów)'}")
print(f"\nWszystkie moduły: jeden projekt Django, jeden proces Pythona (PID {os.getpid()}), jedna baza danych: {db_name}")
print("Komunikacja między modułami: wywołania klas i funkcji w tym samym procesie, a nie żądania sieciowe.")
