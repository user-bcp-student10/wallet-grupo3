import http.client
import json
import re
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import auth
import receipt_pdf
import server

RECEIPT = {
    "receiptId": "rcpt_123",
    "paymentId": "pay_abc123",
    "amountCents": 123456,
    "currency": "PEN",
    "recipient": "merchant-demo",
    "status": "SUCCEEDED",
}
ISSUED = datetime(2026, 10, 23, 21, 30, tzinfo=timezone.utc)


class ReceiptPdfTests(unittest.TestCase):
    def test_builds_a_well_formed_single_page_pdf(self):
        pdf = receipt_pdf.build_receipt_pdf(RECEIPT, ISSUED)

        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertTrue(pdf.rstrip().endswith(b"%%EOF"))
        self.assertEqual(pdf.count(b"/Type /Page "), 1)
        startxref = int(re.search(rb"startxref\n(\d+)\n%%EOF", pdf).group(1))
        self.assertTrue(pdf[startxref:].startswith(b"xref\n0 7"))
        for number, offset in enumerate(re.findall(rb"(\d{10}) 00000 n", pdf), 1):
            self.assertTrue(pdf[int(offset):].startswith(f"{number} 0 obj".encode()))

    def test_stream_length_matches_content(self):
        pdf = receipt_pdf.build_receipt_pdf(RECEIPT, ISSUED)

        length = int(re.search(rb"/Length (\d+)", pdf).group(1))
        body = pdf.split(b"stream\n", 1)[1].split(b"\nendstream", 1)[0]
        self.assertEqual(len(body), length)

    def test_includes_amount_status_reference_and_lima_time(self):
        pdf = receipt_pdf.build_receipt_pdf(RECEIPT, ISSUED)

        for expected in (b"S/ 1,234.56", b"EXITOSO", b"pay_abc123", b"rcpt_123", b"23/10/2026 16:30", b"MODO PRUEBA"):
            self.assertIn(expected, pdf)
        self.assertIn("Billetera Per".encode("cp1252") + b"\xfa", pdf)

    def test_formats_small_and_round_amounts(self):
        self.assertEqual(receipt_pdf.format_pen(5), "S/ 0.05")
        self.assertEqual(receipt_pdf.format_pen(100000), "S/ 1,000.00")

    def test_reversed_receipt_is_labeled(self):
        pdf = receipt_pdf.build_receipt_pdf({**RECEIPT, "status": "REVERSED"}, ISSUED)

        self.assertIn(b"REVERSADO", pdf)

    def test_rejects_malformed_receipts(self):
        bad = [
            None,
            {**RECEIPT, "amountCents": "100"},
            {**RECEIPT, "amountCents": 0},
            {**RECEIPT, "currency": "USD"},
            {**RECEIPT, "recipient": "desconocido"},
            {**RECEIPT, "status": "PENDING"},
            {**RECEIPT, "paymentId": "pay) /JS (x"},
            {key: value for key, value in RECEIPT.items() if key != "receiptId"},
        ]
        for receipt in bad:
            with self.assertRaises(receipt_pdf.InvalidReceipt):
                receipt_pdf.build_receipt_pdf(receipt, ISSUED)

    def test_escapes_pdf_special_characters(self):
        self.assertEqual(receipt_pdf._escape("a(b)c\\d"), "a\\(b\\)c\\\\d")

    def test_long_identifiers_are_shortened(self):
        long_id = "p" * 120
        pdf = receipt_pdf.build_receipt_pdf({**RECEIPT, "paymentId": long_id}, ISSUED)

        self.assertNotIn(long_id.encode(), pdf)
        self.assertIn(b"...", pdf)


class ReceiptPdfEndpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_accounts = server._accounts
        server._accounts = auth.AccountStore(Path(self.tmp.name) / "accounts.sqlite3")
        self.mock_result = (200, dict(RECEIPT))
        patcher = patch("server.request_mock", side_effect=self.fake_mock)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), server.WalletWebHandler)
        threading.Thread(target=self.http.serve_forever, daemon=True).start()
        self.addCleanup(self.cleanup_server)

    def cleanup_server(self):
        self.http.shutdown()
        self.http.server_close()
        server._accounts = self.original_accounts
        self.tmp.cleanup()

    def fake_mock(self, method, path, payload=None, idempotency_key=None):
        if (method, path) == ("POST", "/kyc/verifications"):
            return 201, {"id": "kyc_1", "wallet_id": "wallet_1", "scenario": "APPROVED", "status": "ACTIVE"}
        if method == "GET" and path.endswith("/receipt"):
            return self.mock_result
        return 404, {"error": "NOT_FOUND"}

    def get(self, path, cookie=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.http.server_port, timeout=5)
        connection.request("GET", path, headers={"Cookie": cookie} if cookie else {})
        response = connection.getresponse()
        body = response.read()
        headers = {name.lower(): value for name, value in response.getheaders()}
        connection.close()
        return response.status, headers, body

    def session_cookie(self):
        token, _ = server.accounts().register(
            {"role": "person", "document": "12345678", "email": "a@example.test", "phone": "912345678", "password": "clave-ficticia"},
            server.create_kyc,
        )
        return f"{server.SESSION_COOKIE}={token}"

    def test_requires_a_session(self):
        status, _, body = self.get("/api/payments/pay_abc123/receipt.pdf")

        self.assertEqual(status, 401)
        self.assertNotIn(b"%PDF", body)

    def test_downloads_the_pdf_as_an_attachment(self):
        status, headers, body = self.get("/api/payments/pay_abc123/receipt.pdf", self.session_cookie())

        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "application/pdf")
        self.assertEqual(headers["content-disposition"], 'attachment; filename="comprobante-pay_abc123.pdf"')
        self.assertEqual(headers["cache-control"], "no-store")
        self.assertEqual(int(headers["content-length"]), len(body))
        self.assertTrue(body.startswith(b"%PDF-1.4"))
        self.assertIn(b"S/ 1,234.56", body)

    def test_not_ready_receipt_returns_a_json_error_not_a_pdf(self):
        self.mock_result = (409, {"error": "RECEIPT_NOT_READY", "interno": "no debe filtrarse"})

        status, headers, body = self.get("/api/payments/pay_abc123/receipt.pdf", self.session_cookie())

        self.assertEqual(status, 409)
        self.assertTrue(headers["content-type"].startswith("application/json"))
        self.assertEqual(json.loads(body), {"error": "RECEIPT_NOT_READY"})

    def test_untrusted_receipt_from_the_mock_is_a_bad_gateway(self):
        self.mock_result = (200, {**RECEIPT, "amountCents": "mucho"})

        status, _, body = self.get("/api/payments/pay_abc123/receipt.pdf", self.session_cookie())

        self.assertEqual(status, 502)
        self.assertEqual(json.loads(body), {"error": "WALLET_SERVICE_UNAVAILABLE"})

    def test_rejects_ids_outside_the_allowed_pattern(self):
        status, _, _ = self.get("/api/payments/pay%20x/receipt.pdf", self.session_cookie())

        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
