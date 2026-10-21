# -*- coding: utf-8 -*-
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
    print(f"  obciążenia klienta w Payment Service: {len(LEDGER)} -> {', '.join(c['payment_id'] for c in LEDGER)}\n")
    return len(LEDGER)


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), PaymentService)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/payments"
    print(f"Payment Service (symulacja): {url}\n")
    bez = scenario(url, "Scenariusz A: ponowienie BEZ klucza idempotencji", use_key=False)
    z = scenario(url, "Scenariusz B: ponowienie Z kluczem Idempotency-Key (ten sam klucz w każdej próbie)", use_key=True)
    print(f"Wynik: bez klucza = {bez} obciążenia (podwójna płatność), z kluczem = {z} obciążenie.")
    server.shutdown()


if __name__ == "__main__":
    main()
