# -*- coding: utf-8 -*-
"""Diagram architektury sklepu (LAB2, zadanie 5) jako SVG - renderowany do PNG przez Playwright."""
from html import escape

W, H = 1400, 860
FONT = "Segoe UI, Arial, sans-serif"
COL = {
    "module": ("#dbeafe", "#1d4ed8"), "service": ("#dcfce7", "#15803d"), "db": ("#f1f5f9", "#475569"),
    "broker": ("#ffedd5", "#c2410c"), "client": ("#f5f3ff", "#6d28d9"), "external": ("#ffffff", "#64748b"),
    "gateway": ("#fef9c3", "#a16207"),
}


def box(x, y, w, h, lines, kind, dashed=False, bold_first=True):
    fill, stroke = COL[kind]
    dash = ' stroke-dasharray="7 5"' if dashed else ""
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="2"{dash}/>']
    n = len(lines)
    for i, t in enumerate(lines):
        ty = y + h / 2 + (i - (n - 1) / 2) * 17 + 5
        weight = "700" if (i == 0 and bold_first) else "400"
        size = 15 if i == 0 else 12
        out.append(f'<text x="{x + w / 2}" y="{ty}" text-anchor="middle" font-size="{size}" font-weight="{weight}" '
                   f'fill="#0f172a">{escape(t)}</text>')
    return "".join(out)


def cylinder(x, y, w, h, lines):
    fill, stroke = COL["db"]
    ry = 12
    out = [f'<path d="M{x},{y + ry} A{w / 2},{ry} 0 0,1 {x + w},{y + ry} L{x + w},{y + h - ry} '
           f'A{w / 2},{ry} 0 0,1 {x},{y + h - ry} Z" fill="{fill}" stroke="{stroke}" stroke-width="2"/>',
           f'<ellipse cx="{x + w / 2}" cy="{y + ry}" rx="{w / 2}" ry="{ry}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>']
    n = len(lines)
    for i, t in enumerate(lines):
        ty = y + ry + (h - ry) / 2 + (i - (n - 1) / 2) * 16 + 5
        out.append(f'<text x="{x + w / 2}" y="{ty}" text-anchor="middle" font-size="{13 if i == 0 else 11.5}" '
                   f'font-weight="{700 if i == 0 else 400}" fill="#0f172a">{escape(t)}</text>')
    return "".join(out)


def arrow(points, sync=True, label=None, lx=None, ly=None, anchor="middle", color="#0f172a", both=False):
    pts = " ".join(f"{x},{y}" for x, y in points)
    dash = "" if sync else ' stroke-dasharray="8 6"'
    marker = "url(#a)" if color == "#0f172a" else "url(#ar)"
    start = f' marker-start="{marker}"' if both else ""
    out = [f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"{dash} marker-end="{marker}"{start}/>']
    if label:
        for i, t in enumerate(label.split("\n")):
            out.append(f'<text x="{lx}" y="{ly + i * 15}" text-anchor="{anchor}" font-size="12" fill="{color}" '
                       f'stroke="#ffffff" stroke-width="4" paint-order="stroke">{escape(t)}</text>')
    return "".join(out)


def line(x1, y1, x2, y2):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#475569" stroke-width="2"/>'


def diagram_svg():
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">',
         '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
         '<path d="M0,0 L10,5 L0,10 z" fill="#0f172a"/></marker>'
         '<marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
         '<path d="M0,0 L10,5 L0,10 z" fill="#b91c1c"/></marker></defs>',
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
         '<text x="40" y="26" font-size="18" font-weight="700" fill="#0f172a">Architektura sklepu: 100 tys. produktów, koszyk, '
         'płatności online, magazyn, dostawa kurierska, konta klientów, zwroty</text>']
    # klient, gateway, bramka platnicza
    s.append(box(40, 50, 230, 70, ["Klient", "przeglądarka / aplikacja mobilna"], "client"))
    s.append(box(400, 50, 300, 70, ["API Gateway / Nginx", "HTTPS, routing, limity zapytań"], "gateway"))
    s.append(box(880, 50, 230, 70, ["Bramka płatnicza", "system zewnętrzny (np. PayU)"], "external", dashed=True))
    # monolit modulowy
    s.append('<rect x="40" y="170" width="770" height="440" rx="14" fill="#f8fafc" stroke="#1e3a8a" stroke-width="2.5"/>')
    s.append('<text x="60" y="198" font-size="16" font-weight="700" fill="#1e3a8a">Sklep – monolit modułowy (Django Oscar), '
             'jedno wdrożenie</text>')
    s.append(box(70, 220, 220, 80, ["Katalog (Product)", "produkty, kategorie, ceny"], "module"))
    s.append(box(315, 220, 220, 80, ["Koszyk (Cart)", "koszyki, pozycje"], "module"))
    s.append(box(560, 220, 220, 80, ["Klienci (Customer)", "konta, adresy"], "module"))
    s.append(box(70, 330, 220, 80, ["Promocje (Offer)", "rabaty, vouchery"], "module"))
    s.append(box(315, 330, 220, 80, ["Zwroty (Returns)", "zgłoszenia, decyzje"], "module"))
    s.append(box(560, 330, 220, 80, ["Zamówienia + Checkout", "Order: zamówienia, statusy"], "module"))
    s.append(cylinder(90, 450, 440, 110, ["PostgreSQL – wspólna baza monolitu",
                                          "osobne schematy modułów: catalogue, basket,",
                                          "customer, offer, returns, order"]))
    s.append('<text x="560" y="470" font-size="12" fill="#334155">moduły wywołują się</text>')
    s.append('<text x="560" y="486" font-size="12" fill="#334155">w jednym procesie (bez sieci);</text>')
    s.append('<text x="560" y="502" font-size="12" fill="#334155">każdy moduł zapisuje tylko</text>')
    s.append('<text x="560" y="518" font-size="12" fill="#334155">do swojego schematu</text>')
    # wydzielone serwisy + ich bazy
    s.append(box(880, 170, 230, 80, ["Payment Service", "płatności, zwroty pieniędzy"], "service"))
    s.append(cylinder(1150, 170, 210, 80, ["DB płatności", "transakcje, klucze idempotencji"]))
    s.append(line(1110, 210, 1150, 210))
    s.append(box(880, 340, 230, 80, ["Inventory Service", "stany, rezerwacje"], "service"))
    s.append(cylinder(1150, 340, 210, 80, ["DB magazynu", "stany, rezerwacje, magazyny"]))
    s.append(line(1110, 380, 1150, 380))
    s.append(box(880, 500, 230, 80, ["Delivery Service", "przesyłki, etykiety, statusy"], "service"))
    s.append(cylinder(1150, 500, 210, 80, ["DB przesyłek", "przesyłki, numery listów"]))
    s.append(line(1110, 540, 1150, 540))
    s.append(box(1150, 620, 210, 56, ["API kuriera", "system zewnętrzny"], "external", dashed=True))
    # broker, powiadomienia, wyszukiwarka
    s.append(box(330, 690, 480, 80, ["Broker zdarzeń (RabbitMQ)",
                                     "OrderCreated · PaymentConfirmed · ReturnApproved · ShipmentStatusChanged"], "broker"))
    s.append(box(880, 690, 230, 80, ["Powiadomienia (worker)", "e-maile do klientów"], "service"))
    s.append(box(40, 690, 250, 80, ["Wyszukiwarka (Elasticsearch)", "indeks 100 tys. produktów"], "service"))
    # strzalki synchroniczne
    s.append(arrow([(270, 85), (398, 85)], True, "HTTPS (sync)", 334, 77))
    s.append(arrow([(550, 120), (550, 168)], True, "HTTP (sync)", 560, 150, anchor="start"))
    s.append(arrow([(780, 355), (830, 355), (830, 215), (878, 215)], True, color="#b91c1c"))
    s.append('<text x="884" y="274" font-size="12" font-weight="700" fill="#b91c1c">↑ REST: autoryzacja płatności (sync)</text>')
    s.append('<text x="884" y="290" font-size="12" fill="#b91c1c">z checkoutu, timeout 5 s</text>')
    s.append(arrow([(780, 385), (878, 385)], True))
    s.append('<text x="884" y="442" font-size="12" font-weight="700" fill="#0f172a">↑ REST: POST /inventory/reservations</text>')
    s.append('<text x="884" y="458" font-size="12" fill="#0f172a">(sync, rezerwacja w checkoucie)</text>')
    s.append(arrow([(960, 170), (960, 122)], True, "sync", 950, 150, anchor="end"))
    s.append(arrow([(1040, 122), (1040, 168)], False, "webhook\n(async)", 1048, 140, anchor="start"))
    s.append(arrow([(1050, 580), (1050, 648), (1148, 648)], True, "sync", 1095, 640))
    # strzalki asynchroniczne
    s.append(arrow([(690, 612), (690, 688)], False, "OrderCreated, ReturnApproved\n(async)", 680, 640, anchor="end"))
    s.append(arrow([(810, 730), (878, 730)], False))
    s.append(arrow([(800, 692), (878, 560)], False, "OrderCreated\n→ wysyłka (async)", 848, 632, anchor="start"))
    s.append(arrow([(330, 730), (292, 730)], False, "ProductUpdated\n→ indeksowanie", 312, 785, anchor="middle"))
    # punkt awarii
    s.append('<line x1="1150" y1="285" x2="1110" y2="246" stroke="#b91c1c" stroke-width="2"/>')
    s.append('<rect x="1150" y="258" width="230" height="64" rx="8" fill="#fee2e2" stroke="#b91c1c" stroke-width="2"/>')
    s.append('<text x="1265" y="280" text-anchor="middle" font-size="13" font-weight="700" fill="#b91c1c">⚠ PUNKT AWARII</text>')
    s.append('<text x="1265" y="297" text-anchor="middle" font-size="11.5" fill="#7f1d1d">Payment / bramka nie odpowiada:</text>')
    s.append('<text x="1265" y="313" text-anchor="middle" font-size="11.5" fill="#7f1d1d">timeout, status płatności nieznany</text>')
    # legenda
    s.append('<rect x="1150" y="700" width="230" height="140" rx="8" fill="#ffffff" stroke="#94a3b8"/>')
    s.append('<text x="1162" y="720" font-size="13" font-weight="700" fill="#0f172a">Legenda</text>')
    s.append(arrow([(1162, 740), (1212, 740)], True))
    s.append('<text x="1220" y="744" font-size="11.5" fill="#0f172a">synchronicznie (REST/HTTP)</text>')
    s.append(arrow([(1162, 762), (1212, 762)], False))
    s.append('<text x="1220" y="766" font-size="11.5" fill="#0f172a">asynchronicznie (zdarzenia)</text>')
    s.append('<rect x="1162" y="776" width="50" height="16" rx="4" fill="#fee2e2" stroke="#b91c1c"/>')
    s.append('<text x="1220" y="789" font-size="11.5" fill="#0f172a">potencjalny punkt awarii</text>')
    s.append('<rect x="1162" y="800" width="50" height="16" rx="4" fill="#fff" stroke="#64748b" stroke-dasharray="5 4"/>')
    s.append('<text x="1220" y="813" font-size="11.5" fill="#0f172a">system zewnętrzny</text>')
    s.append('<rect x="1162" y="822" width="24" height="12" rx="3" fill="#dbeafe" stroke="#1d4ed8"/>')
    s.append('<rect x="1188" y="822" width="24" height="12" rx="3" fill="#dcfce7" stroke="#15803d"/>')
    s.append('<text x="1220" y="833" font-size="11.5" fill="#0f172a">moduł / osobny serwis</text>')
    s.append("</svg>")
    return "".join(s)


def diagram_html():
    return (f"<html><head><meta charset='utf-8'><style>body{{margin:0;background:#fff}}</style></head>"
            f"<body><div id='w' style='width:{W}px;height:{H}px'>{diagram_svg()}</div></body></html>")
