import http.client
import json
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import auth
import server

PAYER = {"role": "person", "document": "11111111", "email": "payer@example.test", "phone": "911111111", "password": "clave-ficticia"}
FRIEND = {"role": "person", "document": "22222222", "email": "friend@example.test", "phone": "922222222", "password": "clave-ficticia"}
SHOP = {"role": "merchant", "document": "20123456786", "email": "shop@example.test", "phone": "933333333", "password": "clave-comercio"}


class FakeClock:
    def __init__(self):
        self.now = 1_000.0

    def __call__(self):
        return self.now


def kyc(status="ACTIVE"):
    return lambda document: {"id": f"kyc_{document}", "wallet_id": f"wallet_{document}", "status": status}


class IdentifierTests(unittest.TestCase):
    def test_classifies_phone_dni_and_ruc(self):
        cases = {
            "987654321": ("phone", "+51987654321"),
            "+51 987-654-321": ("phone", "+51987654321"),
            "12345678": ("dni", "12345678"),
            "test-12345678": ("dni", "12345678"),
            "20123456786": ("ruc", "20123456786"),
        }
        for raw, expected in cases.items():
            self.assertEqual(auth.classify_identifier(raw), expected, raw)

    def test_rejects_values_that_are_not_a_valid_number(self):
        for raw in (None, 12345678, "", "abc", "812345678", "1234567", "20123456787", "9876543210"):
            self.assertIsNone(auth.classify_identifier(raw), raw)

    def test_masks_keep_only_the_last_digits(self):
        self.assertEqual(auth.mask_identifier("phone", "+51987654321"), "celular \u2022\u2022\u2022 \u2022\u2022\u2022 321")
        self.assertEqual(auth.mask_identifier("dni", "12345678"), "DNI \u2022\u2022\u2022\u20225678")
        self.assertEqual(auth.mask_identifier("ruc", "20123456786"), "RUC \u2022\u2022\u2022\u2022\u2022\u2022\u20226786")


class FindRecipientTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = FakeClock()
        self.store = auth.AccountStore(Path(self.tmp.name) / "accounts.sqlite3", clock=self.clock)
        for account in (PAYER, FRIEND, SHOP):
            self.store.register(account, kyc())
        self.payer = {"role": "person", "document": "11111111"}

    def tearDown(self):
        self.tmp.cleanup()

    def test_finds_an_active_account_by_phone_dni_or_ruc(self):
        phone = self.store.find_recipient("922 222 222", self.payer)
        dni = self.store.find_recipient("22222222", self.payer)
        ruc = self.store.find_recipient("20123456786", self.payer)

        self.assertEqual(phone, {"role": "person", "kind": "phone", "label": "Cliente \u00b7 celular \u2022\u2022\u2022 \u2022\u2022\u2022 222"})
        self.assertEqual(dni["label"], "Cliente \u00b7 DNI \u2022\u2022\u2022\u20222222")
        self.assertEqual((ruc["role"], ruc["label"]), ("merchant", "Comercio \u00b7 RUC \u2022\u2022\u2022\u2022\u2022\u2022\u20226786"))

    def test_never_exposes_the_full_number(self):
        found = self.store.find_recipient("922222222", self.payer)

        self.assertNotIn("922222222", json.dumps(found, ensure_ascii=False))
        self.assertNotIn("22222222", json.dumps(found, ensure_ascii=False))

    def test_unknown_and_inactive_accounts_look_the_same(self):
        self.store.register({**FRIEND, "document": "33333333", "email": "off@example.test", "phone": "944444444"}, kyc("PENDING"))

        for number in ("955555555", "944444444"):
            with self.assertRaises(auth.AuthError) as raised:
                self.store.find_recipient(number, self.payer)
            self.assertEqual((raised.exception.code, raised.exception.status), ("RECIPIENT_NOT_FOUND", 404))

    def test_rejects_paying_yourself_and_malformed_numbers(self):
        with self.assertRaises(auth.AuthError) as own:
            self.store.find_recipient("911111111", self.payer)
        with self.assertRaises(auth.AuthError) as bad:
            self.store.find_recipient("123", self.payer)

        self.assertEqual((own.exception.code, own.exception.status), ("SELF_PAYMENT", 400))
        self.assertEqual((bad.exception.code, bad.exception.status), ("INVALID_RECIPIENT", 400))

    def test_limits_repeated_misses_then_recovers(self):
        for _ in range(auth.LOOKUP_LIMIT):
            with self.assertRaises(auth.AuthError):
                self.store.find_recipient("955555555", self.payer)

        with self.assertRaises(auth.AuthError) as blocked:
            self.store.find_recipient("922222222", self.payer)
        self.assertEqual((blocked.exception.code, blocked.exception.status), ("TOO_MANY_ATTEMPTS", 429))

        self.clock.now += auth.LOCKOUT_SECONDS + 1
        self.assertEqual(self.store.find_recipient("922222222", self.payer)["role"], "person")

    def test_remembers_who_each_payment_was_for(self):
        self.store.record_payment_recipient("pay_1", "Cliente \u00b7 DNI \u2022\u2022\u2022\u20222222")
        self.store.record_payment_recipient("pay_1", "otro valor se ignora")

        self.assertEqual(
            self.store.recipient_labels(["pay_1", "pay_2"]),
            {"pay_1": "Cliente \u00b7 DNI \u2022\u2022\u2022\u20222222"},
        )
        self.assertEqual(self.store.recipient_labels([]), {})


class RecipientEndpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_accounts = server._accounts
        server._accounts = auth.AccountStore(Path(self.tmp.name) / "accounts.sqlite3")
        self.mock_calls = []
        patcher = patch("server.request_mock", side_effect=self.fake_mock)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), server.WalletWebHandler)
        threading.Thread(target=self.http.serve_forever, daemon=True).start()
        self.addCleanup(self.cleanup_server)
        self.cookies = {}
        for name, account in (("payer", PAYER), ("friend", FRIEND), ("shop", SHOP)):
            token, _ = server.accounts().register(account, server.create_kyc)
            self.cookies[name] = f"{server.SESSION_COOKIE}={token}"

    def cleanup_server(self):
        self.http.shutdown()
        self.http.server_close()
        server._accounts = self.original_accounts
        self.tmp.cleanup()

    def fake_mock(self, method, path, payload=None, idempotency_key=None):
        self.mock_calls.append((method, path, payload))
        if (method, path) == ("POST", "/kyc/verifications"):
            return 201, {"id": "kyc_1", "wallet_id": "wallet_1", "scenario": "APPROVED", "status": "ACTIVE"}
        if (method, path) == ("POST", "/payments"):
            return 202, {"id": "pay_77", "wallet_id": "wallet-demo", "recipient": payload["recipient"], "amount": payload["amountCents"], "status": "PENDING"}
        if method == "GET" and path.startswith("/payments?walletId="):
            return 200, [
                {"id": "pay_77", "wallet_id": "wallet-demo", "recipient": "contact-demo", "amount": 1500, "status": "SUCCEEDED"},
                {"id": "pay_old", "wallet_id": "wallet-demo", "recipient": "merchant-demo", "amount": 900, "status": "SUCCEEDED"},
            ]
        if (method, path) == ("GET", "/payments/pay_77/receipt"):
            return 200, {"receiptId": "rcpt_77", "paymentId": "pay_77", "amountCents": 1500, "currency": "PEN", "recipient": "contact-demo", "status": "SUCCEEDED"}
        return 404, {"error": "NOT_FOUND"}

    def call(self, method, path, body=None, who=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.http.server_port, timeout=5)
        send = dict(headers or {})
        data = None
        if body is not None:
            data = json.dumps(body)
            send["Content-Type"] = "application/json"
        if who:
            send["Cookie"] = self.cookies[who]
        connection.request(method, path, body=data, headers=send)
        response = connection.getresponse()
        raw = response.read()
        connection.close()
        return response.status, raw

    def json(self, *args, **kwargs):
        status, raw = self.call(*args, **kwargs)
        return status, json.loads(raw)

    def payments_posted(self):
        return [call for call in self.mock_calls if call[:2] == ("POST", "/payments")]

    def test_resolve_requires_a_session_and_an_active_client(self):
        self.assertEqual(self.json("POST", "/api/recipients/resolve", {"identifier": "922222222"})[0], 401)
        status, body = self.json("POST", "/api/recipients/resolve", {"identifier": "911111111"}, who="shop")
        self.assertEqual((status, body), (403, {"error": "PAYMENT_NOT_ALLOWED"}))

    def test_resolve_returns_only_a_masked_label(self):
        status, body = self.json("POST", "/api/recipients/resolve", {"identifier": "+51 922 222 222"}, who="payer")

        self.assertEqual(status, 200)
        self.assertEqual(body["role"], "person")
        self.assertEqual(set(body), {"role", "kind", "label"})
        self.assertNotIn("922222222", json.dumps(body))

    def test_resolve_errors(self):
        self.assertEqual(self.json("POST", "/api/recipients/resolve", {"identifier": "955555555"}, who="payer"), (404, {"error": "RECIPIENT_NOT_FOUND"}))
        self.assertEqual(self.json("POST", "/api/recipients/resolve", {"identifier": "911111111"}, who="payer"), (400, {"error": "SELF_PAYMENT"}))
        self.assertEqual(self.json("POST", "/api/recipients/resolve", {"identifier": "12"}, who="payer"), (400, {"error": "INVALID_RECIPIENT"}))
        self.assertEqual(self.json("POST", "/api/recipients/resolve", {"identifier": "922222222", "extra": 1}, who="payer"), (400, {"error": "INVALID_REQUEST"}))

    def test_payment_to_a_person_goes_to_contact_demo_and_is_labeled(self):
        body = {"recipientNumber": "922222222", "amountCents": 1500}
        status, payment = self.json("POST", "/api/payments", body, who="payer", headers={"Idempotency-Key": "k1"})

        self.assertEqual(status, 202)
        self.assertEqual(self.payments_posted()[0][2]["recipient"], "contact-demo")
        self.assertNotIn("recipientNumber", self.payments_posted()[0][2])
        self.assertEqual(payment["recipientLabel"], "Cliente \u00b7 celular \u2022\u2022\u2022 \u2022\u2022\u2022 222")

    def test_payment_to_a_merchant_goes_to_merchant_demo(self):
        self.json("POST", "/api/payments", {"recipientNumber": "20123456786", "amountCents": 500}, who="payer", headers={"Idempotency-Key": "k2"})

        self.assertEqual(self.payments_posted()[0][2]["recipient"], "merchant-demo")

    def test_invalid_recipient_never_reaches_the_mock(self):
        for number in ("955555555", "911111111", "xx"):
            status, _ = self.json("POST", "/api/payments", {"recipientNumber": number, "amountCents": 500}, who="payer", headers={"Idempotency-Key": "k3"})
            self.assertIn(status, (400, 404))
        status, body = self.json(
            "POST", "/api/payments",
            {"recipientNumber": "922222222", "recipient": "merchant-demo", "amountCents": 500},
            who="payer", headers={"Idempotency-Key": "k4"},
        )
        self.assertEqual((status, body), (400, {"error": "INVALID_FIELDS"}))
        self.assertEqual(self.payments_posted(), [])

    def test_history_and_receipt_show_the_label_only_for_known_payments(self):
        self.json("POST", "/api/payments", {"recipientNumber": "922222222", "amountCents": 1500}, who="payer", headers={"Idempotency-Key": "k5"})

        _, history = self.json("GET", "/api/payments?walletId=wallet-demo", who="payer")
        _, receipt = self.json("GET", "/api/payments/pay_77/receipt", who="payer")

        self.assertEqual(history[0]["recipientLabel"], "Cliente \u00b7 celular \u2022\u2022\u2022 \u2022\u2022\u2022 222")
        self.assertNotIn("recipientLabel", history[1])
        self.assertEqual(receipt["recipientLabel"], history[0]["recipientLabel"])

    def test_pdf_uses_the_recipient_label(self):
        self.json("POST", "/api/payments", {"recipientNumber": "922222222", "amountCents": 1500}, who="payer", headers={"Idempotency-Key": "k6"})

        status, pdf = self.call("GET", "/api/payments/pay_77/receipt.pdf", who="payer")

        self.assertEqual(status, 200)
        self.assertIn("Cliente \u00b7 celular \u2022\u2022\u2022 \u2022\u2022\u2022 222".encode("cp1252"), pdf)
        self.assertNotIn(b"contact-demo", pdf)


if __name__ == "__main__":
    unittest.main()
