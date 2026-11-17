"""Excel review workbook for the approver: one file with everything needed to sign off."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from cashapp.config import Config
from cashapp.data import Inputs
from cashapp.matching import EXCEPTION, Plan, Result
from cashapp.money import D

HEAD = PatternFill("solid", fgColor="1F3864")
HEAD_FONT = Font(bold=True, color="FFFFFF")
MONEY = '#,##0.00;(#,##0.00);"-"'
MONEY_COLS = {
    "amount",
    "cash_applied",
    "adjustments",
    "on_account",
    "unapplied",
    "debit",
    "credit",
    "open_before",
    "open_after",
}


def _sheet(
    wb: Workbook, title: str, rows: list[dict], widths: dict[str, int] | None = None
) -> None:
    ws = wb.create_sheet(title)
    if not rows:
        ws.append(["(none)"])
        return
    cols = list(rows[0].keys())
    ws.append(cols)
    for c in ws[1]:
        c.fill, c.font = HEAD, HEAD_FONT
    for r in rows:
        ws.append([float(D(r[k])) if k in MONEY_COLS and r[k] != "" else r[k] for k in cols])
    for i, k in enumerate(cols, 1):
        letter = get_column_letter(i)
        ws.column_dimensions[letter].width = (widths or {}).get(k, max(12, min(40, len(k) + 4)))
        if k in MONEY_COLS:
            for cell in ws[letter][1:]:
                cell.number_format = MONEY
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions


def build_workbook(
    run_dir: Path,
    results: list[Result],
    inputs: Inputs,
    plans: dict[str, Plan],
    decisions: dict[str, str],
    lines: list[dict],
    ar_rows: list[dict],
    f: dict,
    res_doc: dict,
    cfg: Config,
) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws.append([f"{cfg.company}: cash application {f['value_date']}  (run {run_dir.name})"])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append(["Status: PENDING APPROVAL. Nothing is posted until a named approver signs off."])
    ws.append([])
    rows = [
        ("Deposits", f["deposit_count"], D(f["deposit_total"])),
        ("Auto-matched", f["auto_count"], D(f["auto_amount"])),
        ("Exceptions", f["exception_count"], D(f["exception_amount"])),
        ("Cash applied to open items", "", D(f["cash_applied"])),
        ("On-account credits", "", D(f["on_account"])),
        ("Left in Unapplied Cash", f["left_unapplied_count"], D(f["left_unapplied"])),
        ("Deductions to 120300", "", D(f["deductions_reclassed"])),
        ("Small-balance write-offs", "", D(f["small_balance_writeoffs"])),
        ("Wire bank fees", "", D(f["bank_fees"])),
        ("Journal total debits", f["journal_entries"], D(f["journal_total_debits"])),
    ]
    ws.append(["Measure", "Count", "Amount (USD)"])
    for c in ws[4]:
        c.fill, c.font = HEAD, HEAD_FONT
    for label, n, amt in rows:
        ws.append([label, n, float(amt)])
        ws.cell(ws.max_row, 3).number_format = MONEY
    ws.append([])
    ws.append(
        [
            "Auto-match rate",
            f["auto_rate_count_pct"] + " by count",
            f["auto_rate_value_pct"] + " by value",
        ]
    )
    for col, w in zip("ABC", (34, 16, 20), strict=True):
        ws.column_dimensions[col].width = w

    _sheet(
        wb,
        "Applications",
        [
            {
                "deposit_id": r.deposit.deposit_id,
                "payer_name": r.deposit.payer_name,
                "method": r.deposit.method,
                "amount": f"{r.deposit.amount}",
                "customer_id": plans[r.deposit.deposit_id].customer_id,
                "rule": r.rule,
                "decision": decisions[r.deposit.deposit_id],
                "docs": "|".join(d for d, _ in plans[r.deposit.deposit_id].applications),
                "cash_applied": f"{plans[r.deposit.deposit_id].applied}",
                "on_account": f"{plans[r.deposit.deposit_id].on_account}",
                "unapplied": f"{plans[r.deposit.deposit_id].unapplied}",
            }
            for r in results
        ],
        {"payer_name": 32, "docs": 30, "decision": 34},
    )
    rat = {x["exception_id"]: x for x in res_doc.get("resolutions", [])}
    exc_rows = []
    for r in results:
        if r.status != EXCEPTION:
            continue
        x = rat.get(r.exception_id, {})
        exc_rows.append(
            {
                "exception_id": r.exception_id,
                "type": r.exception_type,
                "payer_name": r.deposit.payer_name,
                "amount": f"{r.deposit.amount}",
                "recommended_option": x.get("option_id", ""),
                "rationale": x.get("rationale", ""),
                "follow_up": x.get("follow_up", ""),
                "owner": x.get("owner", ""),
            }
        )
    _sheet(
        wb,
        "Exceptions",
        exc_rows,
        {"rationale": 80, "follow_up": 50, "payer_name": 30, "recommended_option": 30},
    )
    ws = wb["Exceptions"]
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    _sheet(wb, "Journal", lines, {"account_name": 34, "memo": 24})
    _sheet(wb, "AR After", ar_rows)
    path = run_dir / f"cash_application_{f['value_date']}.xlsx"
    wb.save(path)
    return path
