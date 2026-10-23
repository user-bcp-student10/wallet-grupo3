"""Serve the payer prototype through a fixed group-3 wallet mock adapter."""

import json
import os
from http.cookies import CookieError, SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import parse_qs, urlsplit

import auth
import receipt_pdf


APP_DIR = Path(__file__).resolve().parents[3] / "apps" / "payer-web"
MOCK_BASE_URL = "https://bcp-wallet-mock.yefri.workers.dev/groups/3"
MOCK_WALLET_PATH = "/wallets/wallet-demo"
MOCK_TIMEOUT_SECONDS = 5
MAX_RESPONSE_BYTES = 16_384
VALID_WALLET_STATES = {"ACTIVE", "PENDING", "REJECTED"}
VALID_PAYMENT_STATES = {"PENDING", "SUCCEEDED", "REJECTED", "REVERSED"}
VALID_RECIPIENTS = {"contact-demo", "merchant-demo"}
PAYMENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,200}$")
SESSION_COOKIE = "wallet_session"
# El mock solo admite estos dos destinos; el número identifica a quién va dirigido el pago en esta app.
MOCK_RECIPIENT_BY_ROLE = {"person": "contact-demo", "merchant": "merchant-demo"}

_accounts = None


def accounts():
    global _accounts
    if _accounts is None:
        _accounts = auth.AccountStore()
    return _accounts


class WalletProxyError(Exception):
    """Raised when the fixed upstream wallet response cannot be trusted."""


def request_mock(method: str, path: str, payload=None, idempotency_key=None):
    body = None
    headers = {
        "Accept": "application/json",
        "User-Agent": "payer-web-demo/1.0",
        "X-Mock-Latency-Ms": "0",
    }
    if payload is not None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key

    request = Request(
        f"{MOCK_BASE_URL}{path}",
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urlopen(request, timeout=MOCK_TIMEOUT_SECONDS) as response:
            status = response.status
            response_body = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as error:
        status = error.code
        response_body = error.read(MAX_RESPONSE_BYTES + 1)
    except (URLError, TimeoutError, OSError) as error:
        raise WalletProxyError("Wallet service unavailable") from error

    if len(response_body) > MAX_RESPONSE_BYTES:
        raise WalletProxyError("Wallet response too large")
    try:
        response_payload = json.loads(response_body) if response_body else {}
    except (UnicodeDecodeError, ValueError) as error:
        raise WalletProxyError("Invalid wallet response") from error
    return status, response_payload


def get_demo_wallet() -> dict:
    status, wallet = request_mock("GET", MOCK_WALLET_PATH)
    if status != 200:
        raise WalletProxyError("Wallet service unavailable")
    if not isinstance(wallet, dict):
        raise WalletProxyError("Invalid wallet response")

    required = {"id", "status", "balance", "reserved", "available", "currency"}
    if not required.issubset(wallet):
        raise WalletProxyError("Invalid wallet response")
    if wallet["id"] != "wallet-demo" or wallet["currency"] != "PEN":
        raise WalletProxyError("Unexpected wallet response")
    if not isinstance(wallet["status"], str) or wallet["status"] not in VALID_WALLET_STATES or any(
        type(wallet[field]) is not int
        for field in ("balance", "reserved", "available")
    ):
        raise WalletProxyError("Invalid wallet response")
    if wallet["available"] != wallet["balance"] - wallet["reserved"]:
        raise WalletProxyError("Inconsistent wallet response")
    return wallet


def validate_payment_request(payload, idempotency_key):
    if not isinstance(payload, dict):
        raise ValueError("INVALID_BODY")
    if set(payload) - {"walletId", "recipient", "amountCents", "currency"}:
        raise ValueError("INVALID_FIELDS")
    if payload.get("walletId", "wallet-demo") != "wallet-demo":
        raise ValueError("INVALID_WALLET")
    recipient = payload.get("recipient")
    if not isinstance(recipient, str) or recipient not in VALID_RECIPIENTS:
        raise ValueError("INVALID_RECIPIENT")
    amount_cents = payload.get("amountCents")
    if type(amount_cents) is not int or not 1 <= amount_cents <= 100_000_000:
        raise ValueError("INVALID_AMOUNT")
    if payload.get("currency", "PEN") != "PEN":
        raise ValueError("INVALID_CURRENCY")
    if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 200:
        raise ValueError("INVALID_IDEMPOTENCY_KEY")

    return {
        "walletId": "wallet-demo",
        "recipient": recipient,
        "amountCents": amount_cents,
        "currency": "PEN",
    }


def public_payment(payment):
    if not isinstance(payment, dict):
        raise WalletProxyError("Invalid payment response")
    required = {"id", "wallet_id", "recipient", "amount", "status"}
    if not required.issubset(payment):
        raise WalletProxyError("Invalid payment response")
    if (
        not isinstance(payment["id"], str)
        or payment["wallet_id"] != "wallet-demo"
        or not isinstance(payment["recipient"], str)
        or payment["recipient"] not in VALID_RECIPIENTS
        or type(payment["amount"]) is not int
        or not isinstance(payment["status"], str)
        or payment["status"] not in VALID_PAYMENT_STATES
    ):
        raise WalletProxyError("Invalid payment response")
    return {
        "id": payment["id"],
        "walletId": payment["wallet_id"],
        "recipient": payment["recipient"],
        "amountCents": payment["amount"],
        "status": payment["status"],
    }


def public_payment_response(payload):
    if isinstance(payload, dict) and "id" in payload:
        return public_payment(payload)
    if isinstance(payload, dict) and payload.get("status") == "PENDING":
        return {"status": "PENDING", "escalated": payload.get("escalated", False)}
    if isinstance(payload, dict) and "error" in payload:
        error = {"error": payload["error"]}
        for field in ("paymentId", "processed", "status"):
            if field in payload:
                error[field] = payload[field]
        return error
    raise WalletProxyError("Invalid payment response")


def create_payment(payload, idempotency_key):
    request_body = validate_payment_request(payload, idempotency_key)
    status, result = request_mock(
        "POST",
        "/payments",
        payload=request_body,
        idempotency_key=idempotency_key,
    )
    return status, public_payment_response(result)


def get_payment_history(wallet_id="wallet-demo"):
    if wallet_id != "wallet-demo":
        raise ValueError("INVALID_WALLET")
    status, payments = request_mock(
        "GET", "/payments?walletId=wallet-demo"
    )
    if status != 200 or not isinstance(payments, list):
        raise WalletProxyError("Invalid payment history response")
    return status, [public_payment(payment) for payment in payments]


def get_payment(payment_id):
    if not isinstance(payment_id, str) or not PAYMENT_ID_PATTERN.fullmatch(payment_id):
        raise ValueError("INVALID_PAYMENT_ID")
    status, result = request_mock("GET", f"/payments/{payment_id}")
    return status, public_payment_response(result)


def resolve_payment(payment_id):
    if not isinstance(payment_id, str) or not PAYMENT_ID_PATTERN.fullmatch(payment_id):
        raise ValueError("INVALID_PAYMENT_ID")
    status, result = request_mock("POST", f"/payments/{payment_id}/resolve")
    return status, public_payment_response(result)


def get_payment_receipt(payment_id):
    if not isinstance(payment_id, str) or not PAYMENT_ID_PATTERN.fullmatch(payment_id):
        raise ValueError("INVALID_PAYMENT_ID")
    status, receipt = request_mock("GET", f"/payments/{payment_id}/receipt")
    if status >= 400:
        return status, receipt
    required = {"receiptId", "paymentId", "amountCents", "currency", "recipient", "status"}
    if not isinstance(receipt, dict) or not required.issubset(receipt):
        raise WalletProxyError("Invalid receipt response")
    return status, {key: receipt[key] for key in required}


def get_receipt_pdf(payment_id):
    status, receipt = get_payment_receipt(payment_id)
    if status != 200:
        code = receipt.get("error") if isinstance(receipt, dict) else None
        return status, None, {"error": code if isinstance(code, str) else "RECEIPT_UNAVAILABLE"}
    label = accounts().recipient_labels([payment_id]).get(payment_id)
    try:
        return 200, receipt_pdf.build_receipt_pdf(receipt, recipient_label=label), None
    except receipt_pdf.InvalidReceipt as error:
        raise WalletProxyError("Invalid receipt response") from error


def label_payments(items):
    labels = accounts().recipient_labels([item["id"] for item in items])
    return [{**item, "recipientLabel": labels[item["id"]]} if item["id"] in labels else item for item in items]


def label_result(result):
    if isinstance(result, dict) and isinstance(result.get("id"), str):
        return label_payments([result])[0]
    return result


def label_receipt(receipt):
    label = accounts().recipient_labels([receipt["paymentId"]]).get(receipt["paymentId"])
    return {**receipt, "recipientLabel": label} if label else receipt


def recipient_from_payload(payload, account):
    """Traduce recipientNumber a un destino del mock, resolviéndolo de nuevo en el servidor."""
    if not isinstance(payload, dict) or "recipientNumber" not in payload:
        return payload, None
    if "recipient" in payload:
        raise ValueError("INVALID_FIELDS")
    found = accounts().find_recipient(payload["recipientNumber"], account)
    rest = {key: value for key, value in payload.items() if key != "recipientNumber"}
    rest["recipient"] = MOCK_RECIPIENT_BY_ROLE[found["role"]]
    return rest, found


def remember_recipient(result, found):
    if found is None or not isinstance(result, dict):
        return result
    payment_id = result.get("id") or result.get("paymentId")
    if not isinstance(payment_id, str) or not PAYMENT_ID_PATTERN.fullmatch(payment_id):
        return result
    accounts().record_payment_recipient(payment_id, found["label"])
    return {**result, "recipientLabel": found["label"]} if "id" in result else result


def parse_json_request(handler):
    content_type = handler.headers.get("Content-Type", "").split(";", 1)[0].strip()
    if content_type != "application/json":
        raise ValueError("JSON_REQUIRED")
    try:
        content_length = int(handler.headers.get("Content-Length", "0"))
    except ValueError as error:
        raise ValueError("INVALID_CONTENT_LENGTH") from error
    if not 1 <= content_length <= MAX_RESPONSE_BYTES:
        raise ValueError("INVALID_BODY_SIZE")
    try:
        return json.loads(handler.rfile.read(content_length))
    except (UnicodeDecodeError, ValueError) as error:
        raise ValueError("INVALID_JSON") from error


def payment_id_from_path(path, suffix=""):
    prefix = "/api/payments/"
    if not path.startswith(prefix) or not path.endswith(suffix):
        return None
    payment_id = path[len(prefix):len(path) - len(suffix) if suffix else None]
    return payment_id if PAYMENT_ID_PATTERN.fullmatch(payment_id) else None


def result_for_get(path, query):
    if path == "/api/wallets/wallet-demo" and not query:
        return 200, get_demo_wallet()
    if path == "/api/payments":
        wallet_id = parse_qs(query).get("walletId", ["wallet-demo"])[0]
        status, items = get_payment_history(wallet_id)
        return status, label_payments(items)
    receipt_id = payment_id_from_path(path, "/receipt")
    if receipt_id:
        status, receipt = get_payment_receipt(receipt_id)
        return status, label_receipt(receipt) if status == 200 else receipt
    payment_id = payment_id_from_path(path)
    if payment_id:
        status, result = get_payment(payment_id)
        return status, label_result(result)
    raise ValueError("NOT_FOUND")


def json_error_for_value(error):
    code = str(error)
    status = 404 if code == "NOT_FOUND" else 400
    return status, {"error": code}


def create_kyc(document):
    try:
        status, kyc = request_mock(
            "POST",
            "/kyc/verifications",
            payload={"documentType": "TEST", "document": f"TEST-{document}"},
        )
    except WalletProxyError as error:
        raise auth.AuthError("KYC_UNAVAILABLE", 503) from error
    if (
        status != 201
        or not isinstance(kyc, dict)
        or not isinstance(kyc.get("id"), str)
        or not isinstance(kyc.get("wallet_id"), str)
        or not PAYMENT_ID_PATTERN.fullmatch(kyc["wallet_id"])
        or not isinstance(kyc.get("status"), str)
        or kyc["status"] not in VALID_WALLET_STATES
    ):
        raise auth.AuthError("KYC_UNAVAILABLE", 503)
    return {"id": kyc["id"], "wallet_id": kyc["wallet_id"], "status": kyc["status"]}


def refresh_wallet_status(wallet_id):
    if not PAYMENT_ID_PATTERN.fullmatch(wallet_id):
        return None
    try:
        status, wallet = request_mock("GET", f"/wallets/{wallet_id}")
    except WalletProxyError:
        return None
    state = wallet.get("status") if isinstance(wallet, dict) else None
    if status == 200 and isinstance(state, str) and state in VALID_WALLET_STATES:
        return state
    return None


def session_token(handler):
    try:
        cookie = SimpleCookie(handler.headers.get("Cookie", ""))
    except CookieError:
        return None
    morsel = cookie.get(SESSION_COOKIE)
    return morsel.value if morsel else None


def session_cookie(token, max_age):
    secure = "; Secure" if os.environ.get("WALLET_COOKIE_SECURE") == "1" else ""
    return (
        f"{SESSION_COOKIE}={token}; Max-Age={max_age}; Path=/; HttpOnly; SameSite=Strict{secure}"
    )


class WalletWebHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(APP_DIR), **kwargs)

    def _account(self):
        return accounts().get_session(session_token(self))

    def do_GET(self):
        parsed_path = urlsplit(self.path)
        if parsed_path.path == "/api/auth/me":
            account = self._account()
            if account is None:
                self._send_json(401, {"error": "UNAUTHENTICATED"})
            else:
                self._send_json(200, account)
            return
        if parsed_path.path.startswith("/api/"):
            if self._account() is None:
                self._send_json(401, {"error": "UNAUTHENTICATED"})
                return
            pdf_payment_id = payment_id_from_path(parsed_path.path, "/receipt.pdf")
            if pdf_payment_id:
                self._send_receipt_pdf(pdf_payment_id)
                return
            try:
                status, payload = result_for_get(parsed_path.path, parsed_path.query)
            except ValueError as error:
                status, payload = json_error_for_value(error)
            except WalletProxyError:
                status, payload = 502, {"error": "WALLET_SERVICE_UNAVAILABLE"}
            self._send_json(status, payload)
            return
        super().do_GET()

    def _register(self):
        try:
            token, account = accounts().register(parse_json_request(self), create_kyc)
        except auth.AuthError as error:
            self._send_json(error.status, {"error": error.code})
            return
        except ValueError as error:
            self._send_json(*json_error_for_value(error))
            return
        self._send_json(
            201,
            account,
            [("Set-Cookie", session_cookie(token, auth.SESSION_SECONDS))],
        )

    def _login(self):
        try:
            payload = parse_json_request(self)
            if not isinstance(payload, dict) or set(payload) - {"role", "identifier", "password"}:
                raise ValueError("INVALID_REQUEST")
            token, account = accounts().login(
                payload.get("role"),
                payload.get("identifier"),
                payload.get("password"),
                refresh_wallet_status,
            )
        except auth.AuthError as error:
            self._send_json(error.status, {"error": error.code})
            return
        except ValueError as error:
            self._send_json(*json_error_for_value(error))
            return
        self._send_json(
            200,
            account,
            [("Set-Cookie", session_cookie(token, auth.SESSION_SECONDS))],
        )

    def _logout(self):
        try:
            parse_json_request(self)
        except ValueError as error:
            self._send_json(*json_error_for_value(error))
            return
        accounts().logout(session_token(self))
        self._send_json(200, {"loggedOut": True}, [("Set-Cookie", session_cookie("", 0))])

    def do_POST(self):
        path = urlsplit(self.path).path
        if path == "/api/auth/register":
            self._register()
            return
        if path == "/api/auth/login":
            self._login()
            return
        if path == "/api/auth/logout":
            self._logout()
            return
        account = self._account()
        if account is None:
            self._send_json(401, {"error": "UNAUTHENTICATED"})
            return
        if account["role"] != "person" or account["status"] != "ACTIVE":
            self._send_json(403, {"error": "PAYMENT_NOT_ALLOWED"})
            return
        if path == "/api/recipients/resolve":
            self._resolve_recipient(account)
            return
        if path == "/api/payments":
            idempotency_key = self.headers.get("Idempotency-Key", "")
            try:
                payload = parse_json_request(self)
                payload, found = recipient_from_payload(payload, account)
                status, result = create_payment(payload, idempotency_key)
                result = remember_recipient(result, found)
            except auth.AuthError as error:
                status, result = error.status, {"error": error.code}
            except ValueError as error:
                status, result = json_error_for_value(error)
            except WalletProxyError:
                status, result = 502, {"error": "WALLET_SERVICE_UNAVAILABLE"}
            self._send_json(status, result)
            return
        if path.startswith("/api/payments/") and path.endswith("/resolve"):
            payment_id = payment_id_from_path(path, "/resolve")
            try:
                if payment_id is None:
                    raise ValueError("INVALID_PAYMENT_ID")
                status, result = resolve_payment(payment_id)
                result = label_result(result)
            except ValueError as error:
                status, result = json_error_for_value(error)
            except WalletProxyError:
                status, result = 502, {"error": "WALLET_SERVICE_UNAVAILABLE"}
            self._send_json(status, result)
            return
        self._send_json(404, {"error": "NOT_FOUND"})

    def _resolve_recipient(self, account):
        try:
            payload = parse_json_request(self)
            if not isinstance(payload, dict) or set(payload) != {"identifier"}:
                raise ValueError("INVALID_REQUEST")
            found = accounts().find_recipient(payload["identifier"], account)
        except auth.AuthError as error:
            self._send_json(error.status, {"error": error.code})
            return
        except ValueError as error:
            self._send_json(*json_error_for_value(error))
            return
        self._send_json(200, found)

    def _send_receipt_pdf(self, payment_id):
        try:
            status, pdf, error = get_receipt_pdf(payment_id)
        except ValueError as exc:
            self._send_json(*json_error_for_value(exc))
            return
        except WalletProxyError:
            self._send_json(502, {"error": "WALLET_SERVICE_UNAVAILABLE"})
            return
        if pdf is None:
            self._send_json(status, error)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(pdf)))
        self.send_header("Content-Disposition", f'attachment; filename="comprobante-{payment_id}.pdf"')
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(pdf)

    def _send_json(self, status, payload, extra_headers=()):
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for name, value in extra_headers:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)


def main():
    address = (os.environ.get("HOST", "127.0.0.1"), int(os.environ.get("PORT", "8000")))
    server = ThreadingHTTPServer(address, WalletWebHandler)
    print(f"Payer web listo en http://{address[0]}:{address[1]}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
