"""Synthetic data for Lumina Streaming Co. (fictional).

One business day of bank deposits (2026-11-16) against the AR ledger as of 2026-11-13.
Sixteen planted cases cover every exception the agent must handle; the rest are routine
payments generated from a fixed seed. The answer key for all of them is written to
tests/evals/answer_key.yaml.
"""

from __future__ import annotations

import csv
import json
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import yaml

from cashapp.money import D, s

VALUE_DATE = "2026-11-16"
AS_OF = date(2026, 11, 13)
SEED = 20261116

CUSTOMERS = [
    # id, name, segment, parent, terms, bank aliases
    ("C001", "Kestrel Foods Inc", "Advertiser", "", 30, "KESTREL FOODS INC"),
    ("C002", "Brightline Media Agency LLC", "Agency", "", 45, "BRIGHTLINE MEDIA AGCY"),
    ("C003", "Northstar Media Group", "Agency", "", 45, "NORTHSTAR MEDIA GROUP INC"),
    ("C004", "Orbit Holdings Inc", "Parent company", "", 30, "ORBIT HOLDINGS INC"),
    ("C005", "Orbit Media EMEA Ltd", "Distribution partner", "C004", 60, "ORBIT MEDIA EMEA"),
    ("C006", "Pinecrest Studios", "Content licensee", "", 30, "PINECREST STUDIOS"),
    ("C007", "Harbor Light Films", "Content licensee", "", 30, "HARBOR LIGHT FILMS"),
    ("C008", "Cascade Wireless Corp", "Distribution partner", "", 45, "CASCADE WIRELESS CORP"),
    ("C009", "Vantage TV Systems", "Device partner", "", 45, "VANTAGE TV SYS"),
    ("C010", "Summit Beverage Co", "Advertiser", "", 30, "SUMMIT BEVERAGE CO"),
    ("C011", "Meridian Auto Group", "Advertiser", "", 30, "MERIDIAN AUTO GRP"),
    (
        "C012",
        "Atlas Broadcasting Nordic AB",
        "Content licensee",
        "",
        60,
        "ATLAS BROADCASTING NORDIC",
    ),
    ("C013", "Bluewater Telecom", "Distribution partner", "", 60, "BLUEWATER TELECOM"),
    ("C014", "Ember & Oak Retail", "Advertiser", "", 30, "EMBER AND OAK RETAIL"),
    ("C015", "Quarry Lane Agency", "Agency", "", 45, "QUARRY LANE AGENCY"),
    ("C016", "Solstice Insurance", "Advertiser", "", 30, "SOLSTICE INSURANCE CO"),
    ("C017", "Tidewater Cable", "Distribution partner", "", 45, "TIDEWATER CABLE"),
    ("C018", "Greenfield Pet Co", "Advertiser", "", 30, "GREENFIELD PET CO"),
    ("C019", "Halcyon Pictures APAC", "Content licensee", "", 60, "HALCYON PICTURES APAC"),
    ("C020", "Ironbridge Financial", "Advertiser", "", 30, "IRONBRIDGE FINANCIAL"),
    ("C021", "Crescent Sports Network", "Content licensee", "", 45, "CRESCENT SPORTS NETWORK"),
    ("C022", "Lumen Devices", "Device partner", "", 45, "LUMEN DEVICES INC"),
    ("C023", "Redwood Outfitters", "Advertiser", "", 30, "REDWOOD OUTFITTERS"),
    ("C024", "Polaris Mobile", "Distribution partner", "", 45, "POLARIS MOBILE"),
    ("C025", "Maple & Main Agency", "Agency", "", 45, "MAPLE AND MAIN AGENCY"),
]
TERMS = {c[0]: c[4] for c in CUSTOMERS}
NAMES = {c[0]: c[1] for c in CUSTOMERS}
ALIAS = {c[0]: c[5] for c in CUSTOMERS}


@dataclass
class Doc:
    doc_id: str
    cust: str
    due: str
    amount: Decimal
    doc_type: str = "INV"
    status: str = "OPEN"
    closed_date: str = ""
    closed_by_ref: str = ""
    doc_date: str = ""
    open_amount: Decimal | None = None

    def row(self) -> dict:
        doc_date = self.doc_date or str(
            date.fromisoformat(self.due) - timedelta(days=TERMS[self.cust])
        )
        open_amt = Decimal("0.00") if self.status == "CLOSED" else (self.open_amount or self.amount)
        return {
            "doc_id": self.doc_id,
            "doc_type": self.doc_type,
            "customer_id": self.cust,
            "doc_date": doc_date,
            "due_date": self.due,
            "po_number": f"PO-{self.cust[1:]}{self.doc_id[-4:]}",
            "original_amount": s(self.amount),
            "open_amount": s(open_amt),
            "status": self.status,
            "closed_date": self.closed_date,
            "closed_by_ref": self.closed_by_ref,
        }


@dataclass
class Dep:
    method: str
    amount: Decimal
    payer: str
    text: str
    case: str
    expect: dict
    remit: list[tuple[str, Decimal, Decimal, str]] = field(default_factory=list)


def _planted() -> tuple[list[Doc], list[Dep]]:
    docs = [
        # P1 Cascade: EDI remittance with a credit memo
        Doc("INV-24121", "C008", "2026-11-10", D("142350.00")),
        Doc("INV-24122", "C008", "2026-11-14", D("98120.50")),
        Doc("CM-24123", "C008", "2026-11-14", D("-6200.00"), doc_type="CM"),
        # P2 Tidewater: lockbox check, three invoices
        Doc("INV-24131", "C017", "2026-10-31", D("56400.00")),
        Doc("INV-24132", "C017", "2026-11-07", D("61250.75")),
        Doc("INV-24133", "C017", "2026-11-12", D("12980.00")),
        # P3 Summit: no reference, unique two-invoice combination
        Doc("INV-24141", "C010", "2026-10-20", D("18450.00")),
        Doc("INV-24142", "C010", "2026-10-30", D("27300.00")),
        Doc("INV-24143", "C010", "2026-11-05", D("9875.25")),
        Doc("INV-24144", "C010", "2026-12-01", D("41000.00")),
        # P4 Brightline: two combinations match; remittance says October
        Doc("INV-24151", "C002", "2026-10-31", D("30000.00"), doc_date="2026-10-01"),
        Doc("INV-24152", "C002", "2026-11-07", D("18000.00"), doc_date="2026-10-08"),
        Doc("INV-24153", "C002", "2026-12-03", D("24000.00"), doc_date="2026-11-03"),
        Doc("INV-24154", "C002", "2026-12-05", D("24000.00"), doc_date="2026-11-05"),
        # P5 Atlas: wire short by an intermediary bank fee
        Doc("INV-24161", "C012", "2026-11-15", D("215000.00")),
        # P6 Greenfield: small-balance short
        Doc("INV-24171", "C018", "2026-11-11", D("12608.40")),
        # P7 Kestrel: make-good deduction
        Doc("INV-24181", "C001", "2026-11-12", D("85000.00")),
        # P8 Bluewater: first installment of a payment plan
        Doc("INV-24191", "C013", "2026-11-01", D("310000.00")),
        # P9 Meridian: overpayment equal to another open invoice
        Doc("INV-24201", "C011", "2026-11-10", D("62000.00")),
        Doc("INV-24202", "C011", "2026-11-28", D("4750.00")),
        # P11/P12 Northstar
        Doc("INV-24211", "C003", "2026-11-08", D("57420.00")),
        Doc("INV-24212", "C003", "2026-12-02", D("33100.00")),
        # P13 Orbit Media EMEA (subsidiary of Orbit Holdings)
        Doc("INV-24221", "C005", "2026-11-13", D("128640.00")),
        # P14 Pinecrest pays with Harbor Light's invoice number (digits transposed)
        Doc("INV-24518", "C006", "2026-11-09", D("44200.00")),
        Doc("INV-24581", "C007", "2026-11-20", D("61900.00")),
        # P15 Solstice: invoice already paid on Nov 6
        Doc(
            "INV-24231",
            "C016",
            "2026-11-05",
            D("23500.00"),
            status="CLOSED",
            closed_date="2026-11-06",
            closed_by_ref="ACH-1106-4471",
        ),
        Doc("INV-24232", "C016", "2026-12-06", D("18250.00")),
        # P16 Ember & Oak: reference not in AR, amount matches
        Doc("INV-24241", "C014", "2026-11-02", D("7315.60")),
        Doc("INV-24242", "C014", "2026-11-14", D("15880.00")),
    ]
    auto = lambda rule, *d: {"status": "AUTO", "rule": rule, "docs": list(d)}  # noqa: E731

    def exc(etype: str, option: str, acceptable: list[str], mention: list[str], why: str) -> dict:
        return {
            "status": "EXCEPTION",
            "exception_type": etype,
            "expected_option": option,
            "acceptable_options": acceptable,
            "rationale_mentions": mention,
            "why": why,
        }

    deps = [
        Dep(
            "ACH",
            D("234270.50"),
            "CASCADE WIRELESS CORP",
            "EDI 820 REMITTANCE",
            "E01",
            auto("REMITTANCE_ADVICE", "CM-24123", "INV-24121", "INV-24122"),
            [
                ("INV-24121", D("142350.00"), D("0"), ""),
                ("INV-24122", D("98120.50"), D("0"), ""),
                ("CM-24123", D("-6200.00"), D("0"), ""),
            ],
        ),
        Dep(
            "LOCKBOX",
            D("130630.75"),
            "TIDEWATER CABLE",
            "CHECK 88213",
            "E02",
            auto("REMITTANCE_ADVICE", "INV-24131", "INV-24132", "INV-24133"),
            [
                ("INV-24131", D("56400.00"), D("0"), ""),
                ("INV-24132", D("61250.75"), D("0"), ""),
                ("INV-24133", D("12980.00"), D("0"), ""),
            ],
        ),
        Dep(
            "ACH",
            D("37175.25"),
            "SUMMIT BEVERAGE CO",
            "SUMMIT BEV AP PAYMENT",
            "E03",
            auto("MULTI_INVOICE_SUM", "INV-24142", "INV-24143"),
        ),
        Dep(
            "ACH",
            D("48000.00"),
            "BRIGHTLINE MEDIA AGCY",
            "BRIGHTLINE PMT OCT CAMPAIGN SVCS",
            "E04",
            exc(
                "AMBIGUOUS_MATCH",
                "COMBO_1",
                ["COMBO_1"],
                ["oct"],
                "Remittance says October; INV-24151 and INV-24152 are the October invoices",
            ),
        ),
        Dep(
            "WIRE",
            D("214975.00"),
            "ATLAS BROADCASTING NORDIC AB",
            "/INV/INV-24161 LICENSE FEE Q4",
            "E05",
            auto("WIRE_BANK_FEE", "INV-24161"),
        ),
        Dep(
            "ACH",
            D("12600.00"),
            "GREENFIELD PET CO",
            "INV-24171",
            "E06",
            auto("SMALL_BALANCE_WRITEOFF", "INV-24171"),
        ),
        Dep(
            "ACH",
            D("81600.00"),
            "KESTREL FOODS INC",
            "INV-24181 LESS MAKEGOOD DED 4PCT UNDERDELIVERY OCT FLIGHT",
            "E07",
            exc(
                "SHORT_PAY",
                "APPLY_AND_RECLASS_DEDUCTION",
                ["APPLY_AND_RECLASS_DEDUCTION"],
                ["makegood", "ad sales"],
                "Customer-claimed deduction with a reason: reclass to 120300 and route to Ad Sales",
            ),
        ),
        Dep(
            "WIRE",
            D("155000.00"),
            "BLUEWATER TELECOM",
            "INV-24191 INSTALLMENT 1 OF 2 PER AGREED PAYMENT PLAN",
            "E08",
            exc(
                "PARTIAL_PAYMENT",
                "APPLY_PARTIAL_LEAVE_OPEN",
                ["APPLY_PARTIAL_LEAVE_OPEN"],
                ["installment"],
                "Payer states installment 1 of 2; apply and leave the rest open",
            ),
        ),
        Dep(
            "ACH",
            D("66750.00"),
            "MERIDIAN AUTO GRP",
            "INV-24201",
            "E09",
            exc(
                "OVERPAYMENT",
                "APPLY_EXCESS:INV-24202",
                ["APPLY_EXCESS:INV-24202", "APPLY_EXCESS_ON_ACCOUNT"],
                ["INV-24202"],
                "Excess equals the customer's other open invoice exactly",
            ),
        ),
        Dep(
            "ACH",
            D("12345.67"),
            "J SMITH HOLDINGS LLC",
            "PAYMENT",
            "E10",
            exc(
                "UNIDENTIFIED",
                "HOLD_UNAPPLIED",
                ["HOLD_UNAPPLIED"],
                [],
                "No customer, no reference: hold and research",
            ),
        ),
        Dep(
            "ACH",
            D("57420.00"),
            "NRTHSTR MEDIA GRP",
            "ACH CREDIT",
            "E11",
            exc(
                "LOW_CONFIDENCE_CUSTOMER",
                "APPLY_TO_CANDIDATE",
                ["APPLY_TO_CANDIDATE"],
                ["INV-24211"],
                "Abbreviated name plus an exact match to one open invoice",
            ),
        ),
        Dep(
            "ACH",
            D("9870.00"),
            "NORTHSIDE MEDIA GRP LLC",
            "VENDOR PMT",
            "E12",
            exc(
                "LOW_CONFIDENCE_CUSTOMER",
                "HOLD_UNAPPLIED",
                ["HOLD_UNAPPLIED"],
                [],
                "Similar name but a different company; nothing ties the amount to Northstar",
            ),
        ),
        Dep(
            "WIRE",
            D("128640.00"),
            "ORBIT HOLDINGS INC",
            "INV-24221 ON BEHALF OF ORBIT MEDIA EMEA",
            "E13",
            exc(
                "PAYER_MISMATCH",
                "APPLY_TO_REFERENCED_DOC",
                ["APPLY_TO_REFERENCED_DOC"],
                ["parent"],
                "Parent paying its subsidiary's invoice, exact amount",
            ),
        ),
        Dep(
            "ACH",
            D("44200.00"),
            "PINECREST STUDIOS",
            "INV-24581",
            "E14",
            exc(
                "PAYER_MISMATCH",
                "APPLY_TO_PAYER_DOC:INV-24518",
                ["APPLY_TO_PAYER_DOC:INV-24518", "HOLD_UNAPPLIED"],
                ["INV-24518"],
                "Transposed digits: Pinecrest's own INV-24518 matches the amount exactly",
            ),
        ),
        Dep(
            "ACH",
            D("23500.00"),
            "SOLSTICE INSURANCE CO",
            "INV-24231 NOV",
            "E15",
            exc(
                "DUPLICATE_PAYMENT",
                "HOLD_UNAPPLIED",
                ["HOLD_UNAPPLIED"],
                ["already paid"],
                "Invoice was paid on Nov 6; hold and ask the customer about refund or credit",
            ),
        ),
        Dep(
            "ACH",
            D("15880.00"),
            "EMBER AND OAK RETAIL",
            "INV-29999",
            "E16",
            auto("AMOUNT_MATCH", "INV-24242"),
        ),
    ]
    return docs, deps


CLEAN_CUSTOMERS = ["C009", "C015", "C019", "C020", "C021", "C022", "C023", "C024", "C025"]
NOISE_ONLY = ["C001", "C011", "C012", "C013", "C018", "C004"]


def _money(rng: random.Random, lo: int, hi: int) -> Decimal:
    return D(f"{rng.randint(lo, hi)}.{rng.randint(0, 99):02d}")


def _generated(rng: random.Random) -> tuple[list[Doc], list[Dep]]:
    docs: list[Doc] = []
    deps: list[Dep] = []
    n = iter(range(24700, 25999))
    hist = iter(range(23100, 23999))

    def new_doc(cust: str, lo: int, hi: int, due_from: int = -40, due_to: int = 25) -> Doc:
        due = AS_OF + timedelta(days=rng.randint(due_from, due_to))
        d = Doc(f"INV-{next(n)}", cust, str(due), _money(rng, lo, hi))
        docs.append(d)
        return d

    for cust in CLEAN_CUSTOMERS + NOISE_ONLY:
        for _ in range(rng.randint(2, 4)):  # paid history
            due = AS_OF - timedelta(days=rng.randint(20, 90))
            docs.append(
                Doc(
                    f"INV-{next(hist)}",
                    cust,
                    str(due),
                    _money(rng, 3000, 90000),
                    status="CLOSED",
                    closed_date=str(due + timedelta(days=rng.randint(0, 15))),
                    closed_by_ref=f"ACH-{rng.randint(1000, 9999)}",
                )
            )
    for cust in NOISE_ONLY:
        if cust == "C004":
            continue
        for _ in range(rng.randint(1, 2)):
            new_doc(cust, 6000, 120000, 5, 40)

    big = {"C019", "C021", "C022", "C024", "C009"}
    pools: dict[str, list[Doc]] = {}
    for cust in CLEAN_CUSTOMERS:
        lo, hi = (40000, 400000) if cust in big else (2500, 95000)
        pools[cust] = [new_doc(cust, lo, hi) for _ in range(rng.randint(8, 10))]

    plan = (
        ["ACH_REF"] * 9
        + ["WIRE_REF"] * 4
        + ["ACH_NOREF"] * 4
        + ["LOCKBOX_REMIT"] * 3
        + ["ACH_MULTIREF"] * 2
    )
    rng.shuffle(plan)
    for i, kind in enumerate(plan):
        cust = CLEAN_CUSTOMERS[i % len(CLEAN_CUSTOMERS)]
        pool = pools[cust]
        k = (
            1
            if kind in ("ACH_REF", "WIRE_REF", "ACH_NOREF")
            else (2 if kind == "ACH_MULTIREF" else 3)
        )
        k = max(1, min(k, len(pool) - 2))
        chosen = sorted(rng.sample(pool, k), key=lambda d: d.doc_id)
        for d in chosen:
            pool.remove(d)
        amt = sum((d.amount for d in chosen), Decimal("0.00"))
        ids = [d.doc_id for d in chosen]
        payer = ALIAS[cust]
        if kind == "ACH_REF":
            deps.append(
                Dep(
                    "ACH",
                    amt,
                    payer,
                    f"{ids[0]} PO {chosen[0].row()['po_number']}",
                    "E00",
                    {"status": "AUTO", "rule": "INVOICE_REFERENCE", "docs": ids},
                )
            )
        elif kind == "WIRE_REF":
            deps.append(
                Dep(
                    "WIRE",
                    amt,
                    payer,
                    f"/RFB/{ids[0]}",
                    "E00",
                    {"status": "AUTO", "rule": "INVOICE_REFERENCE", "docs": ids},
                )
            )
        elif kind == "ACH_NOREF":
            deps.append(
                Dep(
                    "ACH",
                    amt,
                    payer,
                    f"{payer[:10]} AP PMT",
                    "E00",
                    {"status": "AUTO", "rule": "AMOUNT_MATCH", "docs": ids},
                )
            )
        elif kind == "ACH_MULTIREF":
            deps.append(
                Dep(
                    "ACH",
                    amt,
                    payer,
                    " ".join(ids),
                    "E00",
                    {"status": "AUTO", "rule": "INVOICE_REFERENCE", "docs": ids},
                )
            )
        else:
            deps.append(
                Dep(
                    "LOCKBOX",
                    amt,
                    payer,
                    f"CHECK {rng.randint(10000, 99999)}",
                    "E00",
                    {"status": "AUTO", "rule": "REMITTANCE_ADVICE", "docs": ids},
                    [(d.doc_id, d.amount, D("0"), "") for d in chosen],
                )
            )
    return docs, deps


def generate(root: Path) -> dict:
    rng = random.Random(SEED)
    p_docs, p_deps = _planted()
    g_docs, g_deps = _generated(rng)
    docs = p_docs + g_docs
    deps = p_deps + g_deps
    rng.shuffle(deps)

    out = root / "data" / "synthetic"
    out.mkdir(parents=True, exist_ok=True)

    def write(path: Path, rows: list[dict]) -> None:
        with path.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    write(
        out / "customers.csv",
        [
            {
                "customer_id": c[0],
                "name": c[1],
                "segment": c[2],
                "parent_id": c[3],
                "terms_days": c[4],
                "bank_aliases": c[5],
            }
            for c in CUSTOMERS
        ],
    )
    write(out / "ar_open_items.csv", [d.row() for d in sorted(docs, key=lambda d: d.doc_id)])

    dep_rows, remit_rows, key = [], [], {}
    prefix = {"ACH": "ACH", "WIRE": "WIR", "LOCKBOX": "LBX"}
    for i, d in enumerate(deps, 1):
        dep_id = f"DEP-{VALUE_DATE.replace('-', '')}-{i:03d}"
        ref = f"{prefix[d.method]}-1116-{4000 + i * 7}"
        dep_rows.append(
            {
                "deposit_id": dep_id,
                "value_date": VALUE_DATE,
                "method": d.method,
                "amount": s(d.amount),
                "payer_name": d.payer,
                "remittance_text": d.text,
                "bank_ref": ref,
            }
        )
        for doc_id, paid, ded, reason in d.remit:
            remit_rows.append(
                {
                    "bank_ref": ref,
                    "doc_id": doc_id,
                    "amount_paid": s(paid),
                    "deduction_amount": s(ded),
                    "reason_code": reason,
                }
            )
        key[dep_id] = {"case": d.case, **d.expect}
    write(out / f"bank_deposits_{VALUE_DATE}.csv", dep_rows)
    write(out / f"remittance_advices_{VALUE_DATE}.csv", remit_rows)
    total = sum((d.amount for d in deps), Decimal("0.00"))
    (out / f"bank_statement_{VALUE_DATE}.json").write_text(
        json.dumps(
            {
                "bank": "First Pacific Bank (synthetic)",
                "account": "100100 Operating ****4821",
                "value_date": VALUE_DATE,
                "credit_count": len(deps),
                "credit_total": s(total),
            },
            indent=2,
        )
        + "\n"
    )

    key_path = root / "tests" / "evals" / "answer_key.yaml"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text(
        "# Answer key for the synthetic batch. Generated by scripts/generate_data.py.\n"
        "# Claude Code is denied read access to this file (.claude/settings.json).\n"
        + yaml.safe_dump({"value_date": VALUE_DATE, "deposits": key}, sort_keys=False, width=100)
    )
    return {"deposits": len(deps), "total": s(total), "docs": len(docs)}
