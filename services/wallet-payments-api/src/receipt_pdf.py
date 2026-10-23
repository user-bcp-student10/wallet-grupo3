"""Comprobante de pago en PDF: una página A4 con fuentes estándar y sin dependencias."""

import re
from datetime import datetime, timedelta, timezone

PAGE_WIDTH, PAGE_HEIGHT = 595, 842
LIMA = timezone(timedelta(hours=-5))
MAX_ID_CHARS = 48

ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,200}$")
RECIPIENT_LABELS = {
    "contact-demo": "Persona de prueba (contact-demo)",
    "merchant-demo": "Comercio de prueba (merchant-demo)",
}
STATUS_LABELS = {"SUCCEEDED": "EXITOSO", "REVERSED": "REVERSADO"}
STATUS_COLORS = {
    "SUCCEEDED": {"fill": (0.86, 0.95, 0.84), "text": (0.08, 0.5, 0.24)},
    "REVERSED": {"fill": (0.91, 0.9, 0.95), "text": (0.32, 0.29, 0.37)},
}

VIOLET = (0.48, 0.18, 0.88)
BLUE = (0.18, 0.44, 0.88)
MAGENTA = (0.65, 0.17, 0.85)
INK = (0.12, 0.11, 0.23)
MUTED = (0.4, 0.42, 0.53)
LINE = (0.85, 0.9, 0.96)
WHITE = (1, 1, 1)
AQUA = (0.95, 0.99, 1)


class InvalidReceipt(ValueError):
    """El comprobante recibido no tiene el formato esperado."""


def validate_receipt(receipt):
    if not isinstance(receipt, dict):
        raise InvalidReceipt("INVALID_RECEIPT")
    receipt_id, payment_id = receipt.get("receiptId"), receipt.get("paymentId")
    amount, currency = receipt.get("amountCents"), receipt.get("currency")
    recipient, status = receipt.get("recipient"), receipt.get("status")
    if (
        not isinstance(receipt_id, str)
        or not ID_PATTERN.fullmatch(receipt_id)
        or not isinstance(payment_id, str)
        or not ID_PATTERN.fullmatch(payment_id)
        or type(amount) is not int
        or not 1 <= amount <= 100_000_000
        or currency != "PEN"
        or not isinstance(recipient, str)
        or recipient not in RECIPIENT_LABELS
        or not isinstance(status, str)
        or status not in STATUS_LABELS
    ):
        raise InvalidReceipt("INVALID_RECEIPT")
    return receipt_id, payment_id, amount, recipient, status


def format_pen(cents):
    return f"S/ {cents // 100:,}.{cents % 100:02d}"


def _escape(text):
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _short(value):
    return value if len(value) <= MAX_ID_CHARS else value[: MAX_ID_CHARS - 3] + "..."


def _fill(color):
    return f"{color[0]:.3f} {color[1]:.3f} {color[2]:.3f} rg"


def _stroke(color):
    return f"{color[0]:.3f} {color[1]:.3f} {color[2]:.3f} RG"


def _rect(x, y, width, height, color):
    return f"{_fill(color)} {x} {y} {width} {height} re f\n"


def _text(x, y, value, size, color, bold=False):
    font = "F2" if bold else "F1"
    return f"{_fill(color)} BT /{font} {size} Tf {x} {y} Td ({_escape(value)}) Tj ET\n"


def _content(receipt_id, payment_id, amount, recipient, status, issued_at, recipient_label=None):
    issued = issued_at.astimezone(LIMA).strftime("%d/%m/%Y %H:%M")
    badge = STATUS_COLORS[status]
    parts = [
        _rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, AQUA),
        _rect(0, 702, PAGE_WIDTH, 140, VIOLET),
        _rect(0, 698, PAGE_WIDTH, 4, BLUE),
        _text(48, 800, "Billetera Perú", 14, WHITE, bold=True),
        _text(48, 758, "Comprobante de pago", 30, WHITE, bold=True),
        _rect(444, 790, 103, 24, WHITE),
        _text(456, 798, "MODO PRUEBA", 10, VIOLET, bold=True),
        # Tarjeta principal
        _rect(36, 290, 523, 380, WHITE),
        f"{_stroke(LINE)} 0.8 w 36 290 523 380 re S\n",
        _text(64, 636, "Monto pagado", 11, MUTED),
        _text(64, 592, format_pen(amount), 40, MAGENTA, bold=True),
        _rect(64, 548, 96, 24, badge["fill"]),
        _text(76, 556, STATUS_LABELS[status], 10, badge["text"], bold=True),
    ]
    rows = [
        ("REFERENCIA DEL PAGO", _short(payment_id)),
        ("N° DE COMPROBANTE", _short(receipt_id)),
        ("DESTINATARIO", recipient_label or RECIPIENT_LABELS[recipient]),
        ("MONEDA", "PEN · Sol peruano"),
        ("EMITIDO EL", f"{issued} (hora de Lima)"),
    ]
    y = 512
    for label, value in rows:
        parts.append(f"{_stroke(LINE)} 0.6 w 64 {y + 16} m 531 {y + 16} l S\n")
        parts.append(_text(64, y, label, 8, MUTED, bold=True))
        parts.append(_text(64, y - 17, value, 13, INK))
        y -= 46
    parts += [
        _text(48, 262, "Documento generado por la billetera de prueba del Grupo 3.", 9, MUTED),
        _text(48, 248, "Modo prueba: no tiene validez tributaria ni representa dinero real.", 9, MUTED),
        _text(48, 234, "El monto y el estado provienen del proveedor simulado; la fecha es la de emisión de este PDF.", 9, MUTED),
    ]
    return "".join(parts).encode("cp1252", errors="replace")


def _assemble(content):
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            "/Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> /Contents 4 0 R >>"
        ).encode(),
        f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
    ]
    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_offset = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for offset in offsets:
        pdf += f"{offset:010d} 00000 n \n".encode()
    pdf += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode()
    return bytes(pdf)


def build_receipt_pdf(receipt, issued_at=None, recipient_label=None):
    receipt_id, payment_id, amount, recipient, status = validate_receipt(receipt)
    issued_at = issued_at or datetime.now(timezone.utc)
    label = recipient_label.strip()[:80] if isinstance(recipient_label, str) and recipient_label.strip() else None
    return _assemble(_content(receipt_id, payment_id, amount, recipient, status, issued_at, label))
