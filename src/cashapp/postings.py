"""Turn application plans into balanced journal lines and the AR position after posting."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from cashapp.config import Config
from cashapp.data import Inputs
from cashapp.matching import Plan
from cashapp.money import ZERO, fmt, s


class PlanError(ValueError):
    pass


def check_plans(plans: dict[str, Plan], inputs: Inputs) -> None:
    """Invariants across the whole batch. Raises PlanError on the first breach."""
    deposits = {d.deposit_id: d for d in inputs.deposits}
    used: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for dep_id, plan in plans.items():
        dep = deposits[dep_id]
        if plan.deposit_amount != dep.amount:
            raise PlanError(f"{dep_id}: plan amount differs from the deposit")
        if plan.unapplied < 0:
            raise PlanError(
                f"{dep_id}: applies {fmt(plan.applied)} from a {fmt(dep.amount)} deposit"
            )
        if plan.on_account < 0:
            raise PlanError(f"{dep_id}: negative on-account amount")
        for doc_id, amt in plan.applications:
            used[doc_id] += amt
        for adj in plan.adjustments:
            if adj.amount <= 0:
                raise PlanError(f"{dep_id}: non-positive adjustment on {adj.doc_id}")
            used[adj.doc_id] += adj.amount
    for doc_id, total in used.items():
        doc = inputs.docs.get(doc_id)
        if doc is None:
            raise PlanError(f"{doc_id} is not in AR")
        if not doc.is_open:
            raise PlanError(f"{doc_id} is closed and cannot be applied")
        if abs(total) > abs(doc.open_amount) or (total < 0) != (doc.open_amount < 0):
            raise PlanError(
                f"{doc_id}: {fmt(total)} applied across the batch against {fmt(doc.open_amount)} open"
            )


def journal_lines(plans: dict[str, Plan], inputs: Inputs, cfg: Config) -> list[dict]:
    """One balanced entry per deposit. Unapplied remainder needs no entry (already in 120900)."""
    lines: list[dict] = []
    gl = cfg.gl
    for dep in inputs.deposits:
        plan = plans[dep.deposit_id]
        je = f"JE-{dep.deposit_id}"
        rows: list[tuple[str, Decimal, Decimal, str, str]] = []  # acct, dr, cr, doc, memo
        relieve = plan.applied + plan.on_account
        if relieve != 0:
            rows.append((gl["unapplied_cash"], relieve, ZERO, "", "Relieve unapplied cash"))
        for doc_id, amt in plan.applications:
            memo = "Apply cash" if amt > 0 else "Apply credit memo"
            rows.append(
                (gl["ar_trade"], ZERO if amt > 0 else -amt, amt if amt > 0 else ZERO, doc_id, memo)
            )
        if plan.on_account:
            rows.append((gl["ar_trade"], ZERO, plan.on_account, "ON-ACCOUNT", "On-account credit"))
        for adj in plan.adjustments:
            rows.append(
                (adj.account, adj.amount, ZERO, adj.doc_id, adj.kind.replace("_", " ").title())
            )
            rows.append((gl["ar_trade"], ZERO, adj.amount, adj.doc_id, f"Clear {adj.kind.lower()}"))
        dr = sum((r[1] for r in rows), ZERO)
        cr = sum((r[2] for r in rows), ZERO)
        if dr != cr:
            raise PlanError(f"{je} does not balance: Dr {fmt(dr)} Cr {fmt(cr)}")
        for i, (acct, d, c, doc, memo) in enumerate(rows, 1):
            lines.append(
                {
                    "je_id": je,
                    "line": i,
                    "posting_date": inputs.value_date,
                    "account": acct,
                    "account_name": cfg.gl_names.get(acct, ""),
                    "debit": s(d),
                    "credit": s(c),
                    "customer_id": plan.customer_id,
                    "doc_id": doc,
                    "deposit_id": dep.deposit_id,
                    "memo": memo,
                }
            )
    return lines


def ar_after(plans: dict[str, Plan], inputs: Inputs) -> list[dict]:
    """Every open item touched by the batch, before and after."""
    applied: dict[str, Decimal] = defaultdict(lambda: ZERO)
    adjusted: dict[str, Decimal] = defaultdict(lambda: ZERO)
    by: dict[str, list[str]] = defaultdict(list)
    for dep_id, plan in plans.items():
        for doc_id, amt in plan.applications:
            applied[doc_id] += amt
            by[doc_id].append(dep_id)
        for adj in plan.adjustments:
            adjusted[adj.doc_id] += adj.amount
            if dep_id not in by[adj.doc_id]:
                by[adj.doc_id].append(dep_id)
    out = []
    for doc_id in sorted(set(applied) | set(adjusted)):
        doc = inputs.docs[doc_id]
        after = doc.open_amount - applied[doc_id] - adjusted[doc_id]
        out.append(
            {
                "doc_id": doc_id,
                "customer_id": doc.customer_id,
                "doc_type": doc.doc_type,
                "due_date": doc.due_date,
                "open_before": s(doc.open_amount),
                "cash_applied": s(applied[doc_id]),
                "adjustments": s(adjusted[doc_id]),
                "open_after": s(after),
                "status_after": "CLOSED" if after == 0 else "OPEN",
                "deposits": "|".join(by[doc_id]),
            }
        )
    return out
