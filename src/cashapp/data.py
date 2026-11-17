"""Load the day's inputs and run the tie-outs that must pass before matching."""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from cashapp.money import ZERO, D, fmt


@dataclass(frozen=True)
class Customer:
    customer_id: str
    name: str
    segment: str
    parent_id: str
    terms_days: int
    bank_aliases: tuple[str, ...]


@dataclass(frozen=True)
class Doc:
    """An AR item: an invoice (positive) or credit memo (negative)."""

    doc_id: str
    doc_type: str
    customer_id: str
    doc_date: str
    due_date: str
    po_number: str
    original_amount: Decimal
    open_amount: Decimal
    status: str
    closed_date: str
    closed_by_ref: str

    @property
    def is_open(self) -> bool:
        return self.status == "OPEN" and self.open_amount != ZERO


@dataclass(frozen=True)
class Deposit:
    deposit_id: str
    value_date: str
    method: str
    amount: Decimal
    payer_name: str
    remittance_text: str
    bank_ref: str


@dataclass(frozen=True)
class RemitLine:
    bank_ref: str
    doc_id: str
    amount_paid: Decimal
    deduction_amount: Decimal
    reason_code: str


@dataclass
class Inputs:
    value_date: str
    customers: dict[str, Customer]
    docs: dict[str, Doc]
    deposits: list[Deposit]
    remittances: dict[str, list[RemitLine]]
    statement: dict
    files: list[Path] = field(default_factory=list)
    doc_row_count: int = 0


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def input_paths(data_dir: Path, value_date: str) -> dict[str, Path]:
    return {
        "customers": data_dir / "customers.csv",
        "ar": data_dir / "ar_open_items.csv",
        "deposits": data_dir / f"bank_deposits_{value_date}.csv",
        "remittances": data_dir / f"remittance_advices_{value_date}.csv",
        "statement": data_dir / f"bank_statement_{value_date}.json",
    }


def load_inputs(data_dir: Path, value_date: str) -> Inputs:
    p = input_paths(data_dir, value_date)
    missing = [str(v) for v in p.values() if not v.exists()]
    if missing:
        raise FileNotFoundError(f"Missing input files: {', '.join(missing)}")

    customers = {
        r["customer_id"]: Customer(
            customer_id=r["customer_id"],
            name=r["name"],
            segment=r["segment"],
            parent_id=r["parent_id"],
            terms_days=int(r["terms_days"]),
            bank_aliases=tuple(a for a in r["bank_aliases"].split("|") if a),
        )
        for r in _rows(p["customers"])
    }
    doc_rows = _rows(p["ar"])
    docs = {
        r["doc_id"]: Doc(
            doc_id=r["doc_id"],
            doc_type=r["doc_type"],
            customer_id=r["customer_id"],
            doc_date=r["doc_date"],
            due_date=r["due_date"],
            po_number=r["po_number"],
            original_amount=D(r["original_amount"]),
            open_amount=D(r["open_amount"]),
            status=r["status"],
            closed_date=r["closed_date"],
            closed_by_ref=r["closed_by_ref"],
        )
        for r in doc_rows
    }
    deposits = [
        Deposit(
            deposit_id=r["deposit_id"],
            value_date=r["value_date"],
            method=r["method"],
            amount=D(r["amount"]),
            payer_name=r["payer_name"],
            remittance_text=r["remittance_text"],
            bank_ref=r["bank_ref"],
        )
        for r in _rows(p["deposits"])
    ]
    remittances: dict[str, list[RemitLine]] = {}
    for r in _rows(p["remittances"]):
        remittances.setdefault(r["bank_ref"], []).append(
            RemitLine(
                bank_ref=r["bank_ref"],
                doc_id=r["doc_id"],
                amount_paid=D(r["amount_paid"]),
                deduction_amount=D(r["deduction_amount"]),
                reason_code=r["reason_code"],
            )
        )
    statement = json.loads(p["statement"].read_text())
    return Inputs(
        value_date,
        customers,
        docs,
        deposits,
        remittances,
        statement,
        list(p.values()),
        len(doc_rows),
    )


def validate(inputs: Inputs) -> dict:
    """Tie-outs. Any ERROR blocks matching."""
    checks: list[dict] = []

    def add(check: str, ok: bool, severity: str, detail: str) -> None:
        checks.append({"check": check, "status": "PASS" if ok else severity, "detail": detail})

    total = sum((d.amount for d in inputs.deposits), ZERO)
    ctl_total = D(inputs.statement["credit_total"])
    ctl_count = int(inputs.statement["credit_count"])
    add(
        "deposits_tie_to_bank_statement",
        total == ctl_total and len(inputs.deposits) == ctl_count,
        "ERROR",
        f"{len(inputs.deposits)} deposits totaling {fmt(total)}; bank statement shows "
        f"{ctl_count} credits totaling {fmt(ctl_total)}",
    )
    dup_dep = [k for k, n in Counter(d.deposit_id for d in inputs.deposits).items() if n > 1]
    add("unique_deposit_ids", not dup_dep, "ERROR", f"duplicates: {dup_dep}" if dup_dep else "ok")
    wrong_date = [d.deposit_id for d in inputs.deposits if d.value_date != inputs.value_date]
    add(
        "deposit_value_dates",
        not wrong_date,
        "ERROR",
        f"not dated {inputs.value_date}: {wrong_date}" if wrong_date else "ok",
    )
    non_pos = [d.deposit_id for d in inputs.deposits if d.amount <= 0]
    add("positive_deposits", not non_pos, "ERROR", f"{non_pos}" if non_pos else "ok")
    row_count = inputs.doc_row_count or len(inputs.docs)
    add(
        "unique_doc_ids",
        row_count == len(inputs.docs),
        "ERROR",
        f"{row_count} AR rows, {len(inputs.docs)} unique document IDs",
    )
    bad_sign = [
        d.doc_id
        for d in inputs.docs.values()
        if (d.doc_type == "INV" and d.open_amount < 0)
        or (d.doc_type == "CM" and d.open_amount > 0)
        or abs(d.open_amount) > abs(d.original_amount)
    ]
    add("ar_open_amounts_valid", not bad_sign, "ERROR", f"{bad_sign}" if bad_sign else "ok")
    orphan = [d.doc_id for d in inputs.docs.values() if d.customer_id not in inputs.customers]
    add("ar_customers_exist", not orphan, "ERROR", f"{orphan}" if orphan else "ok")
    refs = {d.bank_ref for d in inputs.deposits}
    stray = [r for r in inputs.remittances if r not in refs]
    add(
        "remittances_link_to_deposits",
        not stray,
        "WARNING",
        f"remittance advices with no deposit: {stray}" if stray else "ok",
    )
    open_total = sum((d.open_amount for d in inputs.docs.values() if d.is_open), ZERO)
    errors = [c for c in checks if c["status"] == "ERROR"]
    return {
        "verdict": "FAIL" if errors else "PASS",
        "checks": checks,
        "deposit_count": len(inputs.deposits),
        "deposit_total": f"{total:.2f}",
        "open_ar_total": f"{open_total:.2f}",
    }
