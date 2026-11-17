"""Load project configuration from config/*.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import yaml

from cashapp.money import D

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Config:
    company: str
    entity: str
    currency: str
    gl: dict[str, str]
    gl_names: dict[str, str]
    auto_apply_min_confidence: float
    name_fuzzy_min: float
    name_auto_min: float
    small_balance_max: Decimal
    bank_fee_max_wire: Decimal
    combo_max_docs: int
    combo_max_candidates: int
    deduction_keywords: tuple[str, ...]
    blocked_approvers: tuple[str, ...]


def load_config(root: Path = ROOT) -> Config:
    company = yaml.safe_load((root / "config" / "company.yaml").read_text())
    match = yaml.safe_load((root / "config" / "matching.yaml").read_text())
    gl = {k: str(v["account"]) for k, v in company["gl_accounts"].items()}
    gl_names = {str(v["account"]): v["name"] for v in company["gl_accounts"].values()}
    return Config(
        company=company["company"],
        entity=company["entity"],
        currency=company["currency"],
        gl=gl,
        gl_names=gl_names,
        auto_apply_min_confidence=float(match["auto_apply_min_confidence"]),
        name_fuzzy_min=float(match["customer_name"]["fuzzy_min"]),
        name_auto_min=float(match["customer_name"]["auto_min"]),
        small_balance_max=D(match["tolerances"]["small_balance_writeoff_max"]),
        bank_fee_max_wire=D(match["tolerances"]["bank_fee_max_wire"]),
        combo_max_docs=int(match["combinations"]["max_docs"]),
        combo_max_candidates=int(match["combinations"]["max_candidates"]),
        deduction_keywords=tuple(k.upper() for k in match["deduction_keywords"]),
        blocked_approvers=tuple(a.lower() for a in company["approval"]["blocked_approver_names"]),
    )
