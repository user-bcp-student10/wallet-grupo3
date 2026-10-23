import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import server


class FakeResponse:
    def __init__(self, payload, status=200):
        self.status = status
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, limit):
        return self.payload[:limit]


class DemoWalletTests(unittest.TestCase):
    def setUp(self):
        self.wallet = {
            "id": "wallet-demo",
            "status": "ACTIVE",
            "balance": 100000,
            "reserved": 7200,
            "available": 92800,
            "currency": "PEN",
        }

    @patch("server.urlopen")
    def test_uses_fixed_group_wallet_and_latency_header(self, mock_urlopen):
        mock_urlopen.return_value = FakeResponse(self.wallet)

        result = server.get_demo_wallet()

        request = mock_urlopen.call_args.args[0]
        self.assertEqual(result, self.wallet)
        self.assertEqual(request.full_url, f"{server.MOCK_BASE_URL}/wallets/wallet-demo")
        self.assertEqual(request.get_header("X-mock-latency-ms"), "0")
        self.assertEqual(request.get_header("User-agent"), "payer-web-demo/1.0")
        self.assertEqual(mock_urlopen.call_args.kwargs["timeout"], 5)

    @patch("server.urlopen")
    def test_rejects_inconsistent_available_balance(self, mock_urlopen):
        self.wallet["available"] = 1
        mock_urlopen.return_value = FakeResponse(self.wallet)

        with self.assertRaises(server.WalletProxyError):
            server.get_demo_wallet()

    @patch("server.urlopen")
    def test_creates_payment_with_fixed_wallet_and_idempotency_key(self, mock_urlopen):
        mock_payment = {
            "id": "pay_demo",
            "wallet_id": "wallet-demo",
            "recipient": "contact-demo",
            "amount": 1500,
            "status": "PENDING",
            "scenario": "APPROVED",
            "idem": "request-1",
            "fingerprint": "internal-value",
        }
        mock_urlopen.return_value = FakeResponse(mock_payment, status=202)

        status, payment = server.create_payment(
            {"recipient": "contact-demo", "amountCents": 1500}, "request-1"
        )

        request = mock_urlopen.call_args.args[0]
        self.assertEqual(status, 202)
        self.assertEqual(payment["status"], "PENDING")
        self.assertNotIn("idem", payment)
        self.assertEqual(request.full_url, f"{server.MOCK_BASE_URL}/payments")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Idempotency-key"), "request-1")
        self.assertEqual(
            json.loads(request.data),
            {
                "walletId": "wallet-demo",
                "recipient": "contact-demo",
                "amountCents": 1500,
                "currency": "PEN",
            },
        )

    @patch("server.urlopen")
    def test_payment_history_is_limited_to_wallet_demo(self, mock_urlopen):
        mock_urlopen.return_value = FakeResponse(
            [
                {
                    "id": "pay_demo",
                    "wallet_id": "wallet-demo",
                    "recipient": "merchant-demo",
                    "amount": 2500,
                    "status": "SUCCEEDED",
                    "idem": "private-key",
                    "fingerprint": "internal-value",
                }
            ]
        )

        status, history = server.get_payment_history()

        request = mock_urlopen.call_args.args[0]
        self.assertEqual(status, 200)
        self.assertEqual(history[0]["amountCents"], 2500)
        self.assertNotIn("idem", history[0])
        self.assertEqual(
            request.full_url,
            f"{server.MOCK_BASE_URL}/payments?walletId=wallet-demo",
        )

    @patch("server.urlopen")
    def test_rejects_invalid_payment_without_calling_mock(self, mock_urlopen):
        with self.assertRaises(ValueError):
            server.create_payment(
                {"recipient": "unknown", "amountCents": 1500}, "request-1"
            )
        mock_urlopen.assert_not_called()

    @patch("server.urlopen")
    def test_resolves_payment_using_fixed_id_path(self, mock_urlopen):
        mock_urlopen.return_value = FakeResponse(
            {"status": "PENDING", "escalated": True}, status=202
        )

        status, result = server.resolve_payment("pay_demo")

        request = mock_urlopen.call_args.args[0]
        self.assertEqual(status, 202)
        self.assertTrue(result["escalated"])
        self.assertEqual(
            request.full_url,
            f"{server.MOCK_BASE_URL}/payments/pay_demo/resolve",
        )
        self.assertEqual(request.get_method(), "POST")

    @patch("server.urlopen")
    def test_does_not_accept_another_wallet_id(self, mock_urlopen):
        self.wallet["id"] = "another-wallet"
        mock_urlopen.return_value = FakeResponse(self.wallet)

        with self.assertRaises(server.WalletProxyError):
            server.get_demo_wallet()


if __name__ == "__main__":
    unittest.main()