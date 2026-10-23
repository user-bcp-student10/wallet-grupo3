import http.client
import json
import sqlite3
import sys
import tempfile
import threading
import unittest
from contextlib import closing
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import auth
import server

PERSON = {
    "role": "person",
    "document": "12345678",
    "email": "Ana@Example.test",
    "phone": "+51 912 345 678",
    "password": "clave-ficticia",
}
MERCHANT = {
    "role": "merchant",
    "document": "20123456786",
    "email": "tienda@example.test",
    "phone": "987654321",
    "password": "clave-comercio",
}


class FakeClock:
    def __init__(self):
        self.now = 1_000.0

    def __call__(self):
        return self.now


def fake_kyc(document):
    return {"id": f"kyc_{document}", "wallet_id": "wallet_new", "status": "ACTIVE"}


class AccountStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "accounts.sqlite3"
        self.clock = FakeClock()
        self.store = auth.AccountStore(self.db_path, clock=self.clock)

    def tearDown(self):
        self.tmp.cleanup()

    def test_register_normalizes_data_and_hashes_password(self):
        token, account = self.store.register(PERSON, fake_kyc)

        self.assertEqual(account["email"], "ana@example.test")
        self.assertEqual(account["document"], "12345678")
        self.assertEqual(account["status"], "ACTIVE")
        self.assertNotIn("password", json.dumps(account))
        self.assertIsNotNone(self.store.get_session(token))
        with closing(sqlite3.connect(self.db_path)) as db:
            phone, stored = db.execute("SELECT phone, password_hash FROM accounts").fetchone()
        self.assertEqual(phone, "+51912345678")
        self.assertNotIn(PERSON["password"], stored)
        self.assertTrue(stored.startswith("scrypt$"))

    def test_document_prefix_is_tolerated_but_not_stored(self):
        _, account = self.store.register({**PERSON, "document": "test-12345678"}, fake_kyc)

        self.assertEqual(account["document"], "12345678")

    def test_migrates_legacy_documents_with_test_prefix(self):
        with closing(sqlite3.connect(self.db_path)) as db, db:
            db.execute(
                "INSERT INTO accounts (role, document, email, phone, password_hash, kyc_id, wallet_id, status, created_at) "
                "VALUES ('person', 'TEST-11112222', 'a@b.test', '+51911111111', 'x', 'k', 'w', 'ACTIVE', 0)"
            )

        auth.AccountStore(self.db_path, clock=self.clock)

        with closing(sqlite3.connect(self.db_path)) as db:
            self.assertEqual(db.execute("SELECT document FROM accounts").fetchone()[0], "11112222")

    def test_rejects_invalid_registration_without_calling_kyc(self):
        calls = []
        for field, value in (
            ("document", "1234567"),
            ("email", "sin-arroba"),
            ("phone", "812345678"),
            ("password", "corta"),
        ):
            with self.assertRaises(auth.AuthError) as raised:
                self.store.register({**PERSON, field: value}, lambda doc: calls.append(doc))
            self.assertEqual(raised.exception.status, 400)
        with self.assertRaises(auth.AuthError):
            self.store.register({**MERCHANT, "document": "20123456787"}, lambda doc: calls.append(doc))
        self.assertEqual(calls, [])

    def test_duplicate_document_email_or_phone_is_rejected_generically(self):
        self.store.register(PERSON, fake_kyc)
        calls = []
        for field, value in (
            ("document", PERSON["document"]),
            ("email", "ANA@example.test "),
            ("phone", "912-345-678"),
        ):
            other = {**PERSON, "document": "TEST-87654321", "email": "otra@example.test", "phone": "922222222"}
            other[field] = value
            with self.assertRaises(auth.AuthError) as raised:
                self.store.register(other, lambda doc: calls.append(doc))
            self.assertEqual((raised.exception.code, raised.exception.status), ("REGISTRATION_REJECTED", 409))
        self.assertEqual(calls, [])

    def test_login_by_document_or_email_and_role_must_match(self):
        self.store.register(PERSON, fake_kyc)

        token, account = self.store.login("person", "test-12345678", PERSON["password"])
        self.assertEqual(account["sessionSecondsLeft"], 300)
        self.store.login("person", "ANA@example.test", PERSON["password"])
        for role, identifier, password in (
            ("merchant", "ana@example.test", PERSON["password"]),
            ("person", "TEST-12345678", "otra-clave"),
            ("person", "TEST-00000000", PERSON["password"]),
        ):
            with self.assertRaises(auth.AuthError) as raised:
                self.store.login(role, identifier, password)
            self.assertEqual(raised.exception.code, "INVALID_CREDENTIALS")
        self.assertIsNotNone(self.store.get_session(token))

    def test_session_expires_after_300_seconds_without_renewal(self):
        self.store.register(PERSON, fake_kyc)
        token, _ = self.store.login("person", PERSON["document"], PERSON["password"])

        self.clock.now += 299
        self.assertEqual(self.store.get_session(token)["sessionSecondsLeft"], 1)
        self.clock.now += 2
        self.assertIsNone(self.store.get_session(token))

    def test_logout_invalidates_session(self):
        self.store.register(PERSON, fake_kyc)
        token, _ = self.store.login("person", PERSON["document"], PERSON["password"])

        self.store.logout(token)

        self.assertIsNone(self.store.get_session(token))

    def test_locks_after_five_failures_and_recovers_after_window(self):
        self.store.register(PERSON, fake_kyc)
        for _ in range(5):
            with self.assertRaises(auth.AuthError):
                self.store.login("person", PERSON["document"], "incorrecta")

        with self.assertRaises(auth.AuthError) as raised:
            self.store.login("person", PERSON["document"], PERSON["password"])
        self.assertEqual((raised.exception.code, raised.exception.status), ("TOO_MANY_ATTEMPTS", 429))

        self.clock.now += 301
        token, _ = self.store.login("person", PERSON["document"], PERSON["password"])
        self.assertIsNotNone(token)

    def test_login_refreshes_wallet_status_from_mock(self):
        self.store.register(PERSON, lambda doc: {"id": "k", "wallet_id": "w", "status": "PENDING"})

        _, account = self.store.login(
            "person", PERSON["document"], PERSON["password"], lambda wallet_id: "ACTIVE"
        )

        self.assertEqual(account["status"], "ACTIVE")


class AuthEndpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_accounts = server._accounts
        server._accounts = auth.AccountStore(Path(self.tmp.name) / "accounts.sqlite3")
        self.mock_calls = []
        patcher = patch("server.request_mock", side_effect=self.fake_mock)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), server.WalletWebHandler)
        thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.cleanup_server)

    def cleanup_server(self):
        self.http.shutdown()
        self.http.server_close()
        server._accounts = self.original_accounts
        self.tmp.cleanup()

    def fake_mock(self, method, path, payload=None, idempotency_key=None):
        self.mock_calls.append((method, path))
        if (method, path) == ("POST", "/kyc/verifications"):
            self.kyc_payload = payload
            return 201, {"id": "kyc_1", "wallet_id": "wallet_1", "scenario": "APPROVED", "status": "ACTIVE"}
        if method == "GET" and path.startswith("/wallets/"):
            return 200, {"id": "wallet_1", "status": "ACTIVE"}
        if (method, path) == ("POST", "/payments"):
            return 202, {
                "id": "pay_1", "wallet_id": "wallet-demo", "recipient": "contact-demo",
                "amount": 1500, "status": "PENDING",
            }
        return 404, {"error": "NOT_FOUND"}

    def call(self, method, path, body=None, cookie=None, extra=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.http.server_port, timeout=5)
        headers = dict(extra or {})
        data = None
        if body is not None:
            data = json.dumps(body)
            headers["Content-Type"] = "application/json"
        if cookie:
            headers["Cookie"] = cookie
        connection.request(method, path, body=data, headers=headers)
        response = connection.getresponse()
        raw = response.read()
        set_cookie = response.getheader("Set-Cookie")
        connection.close()
        return response.status, json.loads(raw) if raw else {}, set_cookie

    def login_cookie(self, role="person", identifier="12345678", password="clave-ficticia"):
        status, _, set_cookie = self.call(
            "POST", "/api/auth/login", {"role": role, "identifier": identifier, "password": password}
        )
        self.assertEqual(status, 200)
        return set_cookie.split(";", 1)[0]

    def test_full_register_login_session_logout_flow(self):
        status, _, _ = self.call("GET", "/api/wallets/wallet-demo")
        self.assertEqual(status, 401)

        status, account, register_cookie = self.call("POST", "/api/auth/register", PERSON)
        self.assertEqual((status, account["status"]), (201, "ACTIVE"))
        self.assertEqual(account["sessionSecondsLeft"], 300)
        self.assertEqual(self.kyc_payload["document"], "TEST-12345678")
        status, me, _ = self.call("GET", "/api/auth/me", cookie=register_cookie.split(";", 1)[0])
        self.assertEqual((status, me["document"]), (200, "12345678"))
        status, duplicate, duplicate_cookie = self.call("POST", "/api/auth/register", PERSON)
        self.assertEqual((status, duplicate, duplicate_cookie), (409, {"error": "REGISTRATION_REJECTED"}, None))
        self.assertEqual(self.mock_calls.count(("POST", "/kyc/verifications")), 1)

        status, error, set_cookie = self.call(
            "POST", "/api/auth/login",
            {"role": "person", "identifier": "TEST-12345678", "password": "mala-clave"},
        )
        self.assertEqual((status, error, set_cookie), (401, {"error": "INVALID_CREDENTIALS"}, None))

        status, account, set_cookie = self.call(
            "POST", "/api/auth/login",
            {"role": "person", "identifier": "TEST-12345678", "password": PERSON["password"]},
        )
        self.assertEqual(status, 200)
        self.assertEqual(account["sessionSecondsLeft"], 300)
        for attribute in ("HttpOnly", "SameSite=Strict", "Max-Age=300"):
            self.assertIn(attribute, set_cookie)
        cookie = set_cookie.split(";", 1)[0]

        status, me, _ = self.call("GET", "/api/auth/me", cookie=cookie)
        self.assertEqual((status, me["document"]), (200, "12345678"))
        self.assertNotIn("password", json.dumps(me))
        status, _, _ = self.call("GET", "/api/wallets/wallet-demo", cookie=cookie)
        self.assertNotEqual(status, 401)

        status, _, cleared = self.call("POST", "/api/auth/logout", {}, cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn("Max-Age=0", cleared)
        status, _, _ = self.call("GET", "/api/auth/me", cookie=cookie)
        self.assertEqual(status, 401)

    def test_payment_requires_active_person_session(self):
        payment = {"recipient": "contact-demo", "amountCents": 1500}
        status, _, _ = self.call("POST", "/api/payments", payment, extra={"Idempotency-Key": "k1"})
        self.assertEqual(status, 401)

        self.call("POST", "/api/auth/register", MERCHANT)
        merchant_cookie = self.login_cookie("merchant", MERCHANT["document"], MERCHANT["password"])
        status, error, _ = self.call(
            "POST", "/api/payments", payment, cookie=merchant_cookie, extra={"Idempotency-Key": "k1"}
        )
        self.assertEqual((status, error), (403, {"error": "PAYMENT_NOT_ALLOWED"}))
        self.assertNotIn(("POST", "/payments"), self.mock_calls)

        self.call("POST", "/api/auth/register", PERSON)
        person_cookie = self.login_cookie()
        status, result, _ = self.call(
            "POST", "/api/payments", payment, cookie=person_cookie, extra={"Idempotency-Key": "k1"}
        )
        self.assertEqual((status, result["status"]), (202, "PENDING"))

    def test_register_requires_json_and_reports_kyc_outage(self):
        status, error, _ = self.call("POST", "/api/auth/register", None)
        self.assertEqual(status, 400)

        with patch("server.request_mock", return_value=(503, {"error": "KYC_UNAVAILABLE"})):
            status, error, _ = self.call("POST", "/api/auth/register", PERSON)
        self.assertEqual((status, error), (503, {"error": "KYC_UNAVAILABLE"}))
        status, _, _ = self.call(
            "POST", "/api/auth/login",
            {"role": "person", "identifier": PERSON["document"], "password": PERSON["password"]},
        )
        self.assertEqual(status, 401)


if __name__ == "__main__":
    unittest.main()
