"""Money helpers. All amounts are Decimal with two places; floats never touch a balance."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def D(value: object) -> Decimal:
    """Parse a number or string into a two-place Decimal."""
    if isinstance(value, Decimal):
        return value.quantize(CENT, rounding=ROUND_HALF_UP)
    text = str(value).strip().replace(",", "").replace("$", "")
    if text in ("", "nan", "None"):
        return ZERO
    return Decimal(text).quantize(CENT, rounding=ROUND_HALF_UP)


def fmt(amount: Decimal) -> str:
    """$1,234.56 (negative as -$1,234.56)."""
    sign = "-" if amount < 0 else ""
    return f"{sign}${abs(amount):,.2f}"


def s(amount: Decimal) -> str:
    """Plain string for CSV/JSON: 1234.56."""
    return f"{D(amount):.2f}"
