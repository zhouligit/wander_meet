"""支付公共：订单号、attach、金额换算。"""

from __future__ import annotations

import secrets
import time
from decimal import Decimal, InvalidOperation


def build_out_trade_no() -> str:
    suffix = secrets.token_hex(3)
    return f"wm_pub_{int(time.time() * 1000)}_{suffix}"


def build_attach(user_public_id: str, qr_id: str, product: str) -> str:
    return f"{user_public_id},{qr_id},{product}"


def yuan_to_fen(yuan: str) -> int:
    try:
        amount = Decimal(str(yuan).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid amount: {yuan}") from exc
    fen = int((amount * 100).quantize(Decimal("1")))
    if fen <= 0:
        raise ValueError("amount must be positive")
    return fen
