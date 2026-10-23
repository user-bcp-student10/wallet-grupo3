"""Cuentas locales de W1: registro validado, contraseñas con scrypt y sesiones de 300 s."""

import hashlib
import hmac
import math
import os
import re
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

SESSION_SECONDS = 300
MAX_FAILED_ATTEMPTS = 5
LOOKUP_LIMIT = 10
LOCKOUT_SECONDS = 300
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
MAX_TRACKED_KEYS = 10_000
DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "accounts.sqlite3"
ROLE_DIGITS = {"person": 8, "merchant": 11}
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
SCRYPT_PARAMS = {"n": 2**14, "r": 8, "p": 1}


class AuthError(Exception):
    def __init__(self, code, status):
        super().__init__(code)
        self.code = code
        self.status = status


def has_valid_ruc_check_digit(digits):
    weights = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    total = sum(int(digit) * weight for digit, weight in zip(digits, weights))
    check = 11 - (total % 11)
    if check == 10:
        check = 0
    elif check == 11:
        check = 1
    return int(digits[10]) == check


def normalize_document(value, role):
    if not isinstance(value, str) or not isinstance(role, str) or role not in ROLE_DIGITS:
        return None
    # El prefijo TEST- solo lo exige el mock; se tolera al escribirlo pero no se guarda.
    digits = value.strip().upper().removeprefix("TEST-")
    if not re.fullmatch(rf"\d{{{ROLE_DIGITS[role]}}}", digits):
        return None
    if role == "merchant" and not has_valid_ruc_check_digit(digits):
        return None
    return digits


def normalize_email(value):
    if not isinstance(value, str):
        return None
    email = value.strip().lower()
    return email if len(email) <= 254 and EMAIL_PATTERN.fullmatch(email) else None


def normalize_phone(value):
    if not isinstance(value, str):
        return None
    compact = re.sub(r"[\s-]", "", value.strip())
    national = compact[3:] if compact.startswith("+51") else compact
    return f"+51{national}" if re.fullmatch(r"9\d{8}", national) else None


def is_valid_password(value):
    return isinstance(value, str) and MIN_PASSWORD_LENGTH <= len(value) <= MAX_PASSWORD_LENGTH


def classify_identifier(value):
    """Devuelve (tipo, valor normalizado) para un celular, DNI o RUC; None si no encaja."""
    if not isinstance(value, str):
        return None
    compact = re.sub(r"[\s-]", "", value.strip().upper().removeprefix("TEST-"))
    compact = compact.removeprefix("+51")
    if re.fullmatch(r"9\d{8}", compact):
        return "phone", f"+51{compact}"
    if re.fullmatch(r"\d{8}", compact):
        return "dni", compact
    if re.fullmatch(r"\d{11}", compact) and has_valid_ruc_check_digit(compact):
        return "ruc", compact
    return None


def mask_identifier(kind, value):
    if kind == "phone":
        return f"celular ••• ••• {value[-3:]}"
    if kind == "dni":
        return f"DNI ••••{value[-4:]}"
    return f"RUC •••••••{value[-4:]}"


def hash_password(password):
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, dklen=32, **SCRYPT_PARAMS)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password, stored):
    try:
        _, salt_hex, digest_hex = stored.split("$")
        expected = bytes.fromhex(digest_hex)
        digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            dklen=len(expected),
            **SCRYPT_PARAMS,
        )
    except ValueError:
        return False
    return hmac.compare_digest(digest, expected)


# Se compara contra este hash cuando la cuenta no existe para igualar tiempos de respuesta.
DUMMY_HASH = hash_password("contraseña-ficticia-de-referencia")


def validate_registration(payload):
    allowed = {"role", "document", "email", "phone", "password"}
    if not isinstance(payload, dict) or set(payload) - allowed:
        raise AuthError("INVALID_REQUEST", 400)
    role = payload.get("role")
    document = normalize_document(payload.get("document"), role)
    email = normalize_email(payload.get("email"))
    phone = normalize_phone(payload.get("phone"))
    password = payload.get("password")
    if not (document and email and phone and is_valid_password(password)):
        raise AuthError("INVALID_REGISTRATION", 400)
    return {
        "role": role,
        "document": document,
        "email": email,
        "phone": phone,
        "password": password,
    }


class AccountStore:
    def __init__(self, db_path=DEFAULT_DB_PATH, clock=time.time):
        self._db_path = Path(db_path)
        self._clock = clock
        self._register_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._sessions = {}
        self._failures = {}
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL CHECK (role IN ('person', 'merchant')),
                    document TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL UNIQUE,
                    phone TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    kyc_id TEXT NOT NULL,
                    wallet_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )
                """
            )
            db.execute("UPDATE accounts SET document = substr(document, 6) WHERE document LIKE 'TEST-%'")
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS payment_recipients (
                    payment_id TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )
                """
            )

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self._db_path)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _digest(token):
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _public(self, row, expires_at=None):
        account = {
            "role": row["role"],
            "document": row["document"],
            "email": row["email"],
            "walletId": row["wallet_id"],
            "status": row["status"],
        }
        if expires_at is not None:
            account["sessionSecondsLeft"] = max(0, math.ceil(expires_at - self._clock()))
        return account

    def _open_session(self, row):
        token = secrets.token_urlsafe(32)
        expires_at = self._clock() + SESSION_SECONDS
        with self._state_lock:
            self._sessions[self._digest(token)] = (row["id"], expires_at)
        return token, self._public(row, expires_at)

    def register(self, payload, create_kyc):
        fields = validate_registration(payload)
        # Se serializa para no crear dos wallets en el mock por el mismo dato duplicado.
        with self._register_lock:
            with self._connect() as db:
                duplicate = db.execute(
                    "SELECT 1 FROM accounts WHERE document = ? OR email = ? OR phone = ? LIMIT 1",
                    (fields["document"], fields["email"], fields["phone"]),
                ).fetchone()
            if duplicate:
                raise AuthError("REGISTRATION_REJECTED", 409)

            kyc = create_kyc(fields["document"])
            try:
                with self._connect() as db:
                    db.execute(
                        """
                        INSERT INTO accounts
                            (role, document, email, phone, password_hash, kyc_id, wallet_id, status, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            fields["role"],
                            fields["document"],
                            fields["email"],
                            fields["phone"],
                            hash_password(fields["password"]),
                            kyc["id"],
                            kyc["wallet_id"],
                            kyc["status"],
                            int(self._clock()),
                        ),
                    )
            except sqlite3.IntegrityError as error:
                raise AuthError("REGISTRATION_REJECTED", 409) from error
            with self._connect() as db:
                row = db.execute(
                    "SELECT * FROM accounts WHERE document = ?", (fields["document"],)
                ).fetchone()
        return self._open_session(row)

    def login(self, role, identifier, password, refresh_status=None):
        if (
            not isinstance(role, str)
            or role not in ROLE_DIGITS
            or not isinstance(identifier, str)
            or not isinstance(password, str)
            or len(password) > MAX_PASSWORD_LENGTH
        ):
            raise AuthError("INVALID_CREDENTIALS", 401)

        typed = identifier.strip()
        by_email = "@" in typed
        lookup = normalize_email(typed) if by_email else normalize_document(typed, role)
        limiter_key = f"{role}:{lookup or typed.lower()[:254]}"
        self._check_lockout(limiter_key)

        row = None
        if lookup:
            column = "email" if by_email else "document"
            with self._connect() as db:
                row = db.execute(
                    f"SELECT * FROM accounts WHERE {column} = ? AND role = ?", (lookup, role)
                ).fetchone()

        valid = verify_password(password, row["password_hash"] if row else DUMMY_HASH)
        if row is None or not valid:
            self._record_failure(limiter_key)
            raise AuthError("INVALID_CREDENTIALS", 401)

        with self._state_lock:
            self._failures.pop(limiter_key, None)

        if refresh_status:
            status = refresh_status(row["wallet_id"])
            if status and status != row["status"]:
                with self._connect() as db:
                    db.execute("UPDATE accounts SET status = ? WHERE id = ?", (status, row["id"]))
                    row = db.execute("SELECT * FROM accounts WHERE id = ?", (row["id"],)).fetchone()

        return self._open_session(row)

    def get_session(self, token):
        if not token:
            return None
        digest = self._digest(token)
        with self._state_lock:
            entry = self._sessions.get(digest)
            if entry and entry[1] <= self._clock():
                del self._sessions[digest]
                entry = None
        if entry is None:
            return None
        with self._connect() as db:
            row = db.execute("SELECT * FROM accounts WHERE id = ?", (entry[0],)).fetchone()
        return self._public(row, entry[1]) if row else None

    def logout(self, token):
        if token:
            with self._state_lock:
                self._sessions.pop(self._digest(token), None)

    def find_recipient(self, identifier, payer):
        parsed = classify_identifier(identifier)
        if parsed is None:
            raise AuthError("INVALID_RECIPIENT", 400)
        kind, value = parsed
        key = f"lookup:{payer['role']}:{payer['document']}"
        self._check_lockout(key, LOOKUP_LIMIT)

        if kind == "phone":
            query, params = "SELECT * FROM accounts WHERE phone = ?", (value,)
        else:
            role = "person" if kind == "dni" else "merchant"
            query, params = "SELECT * FROM accounts WHERE document = ? AND role = ?", (value, role)
        with self._connect() as db:
            row = db.execute(query, params).fetchone()
        # Un destinatario inexistente o no activo se informa igual para no revelar cuál es el caso.
        if row is None or row["status"] != "ACTIVE":
            self._record_failure(key)
            raise AuthError("RECIPIENT_NOT_FOUND", 404)
        if row["document"] == payer["document"] and row["role"] == payer["role"]:
            raise AuthError("SELF_PAYMENT", 400)

        who = "Cliente" if row["role"] == "person" else "Comercio"
        return {
            "role": row["role"],
            "kind": kind,
            "label": f"{who} · {mask_identifier(kind, value)}",
        }

    def record_payment_recipient(self, payment_id, label):
        with self._connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO payment_recipients (payment_id, label, created_at) VALUES (?, ?, ?)",
                (payment_id, label, int(self._clock())),
            )

    def recipient_labels(self, payment_ids):
        ids = list(payment_ids)
        labels = {}
        with self._connect() as db:
            for start in range(0, len(ids), 500):
                chunk = ids[start:start + 500]
                marks = ",".join("?" * len(chunk))
                for row in db.execute(
                    f"SELECT payment_id, label FROM payment_recipients WHERE payment_id IN ({marks})",
                    chunk,
                ):
                    labels[row["payment_id"]] = row["label"]
        return labels

    def _recent_failures(self, key):
        cutoff = self._clock() - LOCKOUT_SECONDS
        return [moment for moment in self._failures.get(key, []) if moment > cutoff]

    def _check_lockout(self, key, limit=MAX_FAILED_ATTEMPTS):
        with self._state_lock:
            recent = self._recent_failures(key)
            if recent:
                self._failures[key] = recent
            else:
                self._failures.pop(key, None)
            if len(recent) >= limit:
                raise AuthError("TOO_MANY_ATTEMPTS", 429)

    def _record_failure(self, key):
        with self._state_lock:
            if len(self._failures) >= MAX_TRACKED_KEYS:
                self._failures = {
                    tracked: moments
                    for tracked in list(self._failures)
                    if (moments := self._recent_failures(tracked))
                }
            self._failures[key] = self._recent_failures(key) + [self._clock()]
