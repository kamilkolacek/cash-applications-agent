"""Deterministic matching of bank deposits to open AR items.

Each deposit runs through a waterfall of rules. A deposit either gets one AUTO plan
(proposed, still subject to human approval) or becomes an EXCEPTION with a fixed menu of
options, each a fully computed plan. Claude chooses among options; it never creates amounts.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field
from decimal import Decimal

from cashapp.config import Config
from cashapp.customers import related, resolve_payer
from cashapp.data import Deposit, Doc, Inputs
from cashapp.money import ZERO, fmt, s

REF = re.compile(r"\b(INV|CM)[\s\-#]?(\d{5})\b", re.IGNORECASE)

AUTO = "AUTO"
EXCEPTION = "EXCEPTION"
HOLD = "HOLD_UNAPPLIED"


# --------------------------------------------------------------------------- plans


@dataclass
class Adjustment:
    doc_id: str
    kind: str  # BANK_FEE | SMALL_BALANCE | DEDUCTION_RECLASS
    amount: Decimal
    account: str


@dataclass
class Plan:
    """How one deposit is applied. Cash applied + on-account + unapplied = deposit amount."""

    deposit_amount: Decimal
    customer_id: str = ""
    applications: list[tuple[str, Decimal]] = field(default_factory=list)
    adjustments: list[Adjustment] = field(default_factory=list)
    on_account: Decimal = ZERO

    @property
    def applied(self) -> Decimal:
        return sum((a for _, a in self.applications), ZERO)

    @property
    def unapplied(self) -> Decimal:
        return self.deposit_amount - self.applied - self.on_account

    def to_dict(self) -> dict:
        return {
            "customer_id": self.customer_id,
            "applications": [{"doc_id": d, "amount": s(a)} for d, a in self.applications],
            "adjustments": [
                {"doc_id": a.doc_id, "kind": a.kind, "amount": s(a.amount), "account": a.account}
                for a in self.adjustments
            ],
            "cash_applied": s(self.applied),
            "on_account": s(self.on_account),
            "unapplied": s(self.unapplied),
        }

    @staticmethod
    def from_dict(d: dict, deposit_amount: Decimal) -> Plan:
        from cashapp.money import D

        return Plan(
            deposit_amount=deposit_amount,
            customer_id=d["customer_id"],
            applications=[(a["doc_id"], D(a["amount"])) for a in d["applications"]],
            adjustments=[
                Adjustment(a["doc_id"], a["kind"], D(a["amount"]), a["account"])
                for a in d["adjustments"]
            ],
            on_account=D(d["on_account"]),
        )


@dataclass
class Option:
    option_id: str
    label: str
    plan: Plan

    def to_dict(self) -> dict:
        return {"option_id": self.option_id, "label": self.label, "plan": self.plan.to_dict()}


@dataclass
class Result:
    deposit: Deposit
    status: str
    rule: str
    confidence: float
    customer_id: str = ""
    name_score: float = 0.0
    exception_type: str = ""
    plan: Plan | None = None
    options: list[Option] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)

    @property
    def exception_id(self) -> str:
        return f"EX-{self.deposit.deposit_id}" if self.status == EXCEPTION else ""


# --------------------------------------------------------------------------- helpers


def _order(docs: list[Doc]) -> list[Doc]:
    """Credit memos first, then invoices oldest due date first."""
    return sorted(docs, key=lambda d: (d.doc_type != "CM", d.due_date, d.doc_id))


def _spread(amount: Decimal, docs: list[Doc]) -> tuple[list[tuple[str, Decimal]], Decimal]:
    """Apply cash oldest-first. Returns applications and cash left over."""
    remaining = amount
    apps: list[tuple[str, Decimal]] = []
    for d in _order(docs):
        if d.open_amount < 0:  # credit memo: consume it fully, it adds cash to apply
            apps.append((d.doc_id, d.open_amount))
            remaining -= d.open_amount
            continue
        take = min(d.open_amount, remaining)
        if take > 0:
            apps.append((d.doc_id, take))
            remaining -= take
    return apps, remaining


def _hold(dep: Deposit, customer_id: str = "") -> Option:
    return Option(
        HOLD,
        "Leave the full deposit in Unapplied Cash (120900) pending research",
        Plan(dep.amount, customer_id),
    )


def _residuals(apps: list[tuple[str, Decimal]], docs: dict[str, Doc]) -> list[tuple[str, Decimal]]:
    return [(d, docs[d].open_amount - a) for d, a in apps if docs[d].open_amount - a > 0]


def _has_deduction_words(text: str, cfg: Config) -> bool:
    up = f" {text.upper()} "
    return any(re.search(rf"\b{re.escape(k)}\b", up) for k in cfg.deduction_keywords)


def _open_docs(customer_id: str, inputs: Inputs) -> list[Doc]:
    return [d for d in inputs.docs.values() if d.customer_id == customer_id and d.is_open]


def _combos(amount: Decimal, docs: list[Doc], cfg: Config) -> list[tuple[Doc, ...]]:
    """Every set of open items (size 1..max_docs) whose open amounts sum to the deposit."""
    pool = _order(docs)[: cfg.combo_max_candidates]
    singles = [(d,) for d in pool if d.open_amount == amount]
    if singles:
        return singles
    found = []
    for k in range(2, cfg.combo_max_docs + 1):
        for combo in itertools.combinations(pool, k):
            if sum((d.open_amount for d in combo), ZERO) == amount:
                found.append(combo)
    return found


def _full_plan(dep: Deposit, cust: str, docs: tuple[Doc, ...] | list[Doc]) -> Plan:
    return Plan(dep.amount, cust, [(d.doc_id, d.open_amount) for d in _order(list(docs))])


def _shortfall_auto(
    dep: Deposit, cust: str, docs: list[Doc], short: Decimal, cfg: Config
) -> tuple[Plan, str] | None:
    """Within-authority shortfall: small balance (any method) or bank fee (wires)."""
    if short <= 0:
        return None
    if short <= cfg.small_balance_max:
        kind, acct, rule = "SMALL_BALANCE", cfg.gl["small_balance"], "SMALL_BALANCE_WRITEOFF"
    elif dep.method == "WIRE" and short <= cfg.bank_fee_max_wire:
        kind, acct, rule = "BANK_FEE", cfg.gl["bank_fees"], "WIRE_BANK_FEE"
    else:
        return None
    apps, _ = _spread(dep.amount, docs)
    last = [d for d, _ in apps][-1]
    return Plan(dep.amount, cust, apps, [Adjustment(last, kind, short, acct)]), rule


# --------------------------------------------------------------------------- exceptions


def _shortfall_exception(
    res: Result,
    apps: list[tuple[str, Decimal]],
    inputs: Inputs,
    cfg: Config,
    deduction: bool,
    reason: str,
) -> Result:
    dep, cust = res.deposit, res.customer_id
    resid = _residuals(apps, inputs.docs)
    short = sum((r for _, r in resid), ZERO)
    res.status, res.confidence = EXCEPTION, 0.0
    res.exception_type = "SHORT_PAY" if deduction else "PARTIAL_PAYMENT"
    res.evidence.append(
        f"Payment is {fmt(short)} less than the open balance of the referenced items"
        + (f"; remittance cites a deduction ({reason})" if deduction else "")
    )
    if deduction:
        res.evidence.append(
            f"Deduction of {fmt(short)} exceeds the agent write-off authority of "
            f"{fmt(cfg.small_balance_max)}; write-off is not an option"
        )
    if deduction:
        res.options.append(
            Option(
                "APPLY_AND_RECLASS_DEDUCTION",
                f"Apply the cash and move the {fmt(short)} deduction to Customer Deductions "
                f"({cfg.gl['deductions']}) for validation by the owning team",
                Plan(
                    dep.amount,
                    cust,
                    apps,
                    [Adjustment(d, "DEDUCTION_RECLASS", r, cfg.gl["deductions"]) for d, r in resid],
                ),
            )
        )
        res.options.append(
            Option(
                "APPLY_LEAVE_OPEN",
                f"Apply the cash and leave {fmt(short)} open on the invoice",
                Plan(dep.amount, cust, apps),
            )
        )
    else:
        res.options.append(
            Option(
                "APPLY_PARTIAL_LEAVE_OPEN",
                f"Apply the cash as a partial payment and leave {fmt(short)} open",
                Plan(dep.amount, cust, apps),
            )
        )
    res.options.append(_hold(dep, cust))
    return res


def _overpayment_exception(res: Result, docs: list[Doc], inputs: Inputs, cfg: Config) -> Result:
    dep, cust = res.deposit, res.customer_id
    base = _full_plan(dep, cust, docs)
    excess = dep.amount - base.applied
    res.status, res.confidence, res.exception_type = EXCEPTION, 0.0, "OVERPAYMENT"
    res.evidence.append(f"Payment exceeds the referenced items by {fmt(excess)}")
    used = {d.doc_id for d in docs}
    for other in _order(_open_docs(cust, inputs)):
        if other.doc_id not in used and other.open_amount == excess:
            res.evidence.append(
                f"{other.doc_id} (due {other.due_date}) is open for exactly {fmt(excess)}"
            )
            res.options.append(
                Option(
                    f"APPLY_EXCESS:{other.doc_id}",
                    f"Apply the referenced items in full and the {fmt(excess)} excess "
                    f"to {other.doc_id}",
                    Plan(dep.amount, cust, base.applications + [(other.doc_id, excess)]),
                )
            )
    res.options.append(
        Option(
            "APPLY_EXCESS_ON_ACCOUNT",
            f"Apply the referenced items in full and hold the {fmt(excess)} excess as an "
            "on-account credit for the customer",
            Plan(dep.amount, cust, base.applications, on_account=excess),
        )
    )
    res.options.append(_hold(dep, cust))
    return res


# --------------------------------------------------------------------------- rules


def _match_remittance(res: Result, inputs: Inputs, cfg: Config) -> Result:
    dep = res.deposit
    lines = inputs.remittances[dep.bank_ref]
    res.rule = "REMITTANCE_ADVICE"
    res.evidence.append(f"Remittance advice {dep.bank_ref} lists {len(lines)} item(s)")
    missing = [ln.doc_id for ln in lines if ln.doc_id not in inputs.docs]
    closed = [
        ln.doc_id for ln in lines if ln.doc_id in inputs.docs and not inputs.docs[ln.doc_id].is_open
    ]
    paid = sum((ln.amount_paid for ln in lines), ZERO)
    cust = inputs.docs[lines[0].doc_id].customer_id if lines[0].doc_id in inputs.docs else ""
    res.customer_id = cust
    if missing or closed or paid != dep.amount:
        res.status, res.confidence, res.exception_type = EXCEPTION, 0.0, "REMITTANCE_MISMATCH"
        if missing:
            res.evidence.append(f"Not found in AR: {', '.join(missing)}")
        if closed:
            res.evidence.append(f"Already closed in AR: {', '.join(closed)}")
        if paid != dep.amount:
            res.evidence.append(f"Advice totals {fmt(paid)}; deposit is {fmt(dep.amount)}")
        res.options.append(_hold(dep, cust))
        return res
    apps = [(ln.doc_id, ln.amount_paid) for ln in lines]
    over = [
        ln.doc_id for ln in lines if abs(ln.amount_paid) > abs(inputs.docs[ln.doc_id].open_amount)
    ]
    if over:
        res.status, res.exception_type = EXCEPTION, "REMITTANCE_MISMATCH"
        res.evidence.append(f"Advice pays more than is open on {', '.join(over)}")
        res.options.append(_hold(dep, cust))
        return res
    if _residuals(apps, inputs.docs):
        deduction = any(ln.deduction_amount > 0 for ln in lines)
        reason = ", ".join(sorted({ln.reason_code for ln in lines if ln.reason_code}))
        return _shortfall_exception(res, apps, inputs, cfg, deduction, reason)
    res.status, res.confidence = AUTO, 1.0
    res.plan = Plan(dep.amount, cust, apps)
    return res


def _match_reference(res: Result, docs: list[Doc], inputs: Inputs, cfg: Config) -> Result:
    dep = res.deposit
    res.rule = "INVOICE_REFERENCE"
    doc_cust = docs[0].customer_id
    res.evidence.append(
        "Remittance references " + ", ".join(f"{d.doc_id} ({d.status.lower()})" for d in docs)
    )

    closed = [d for d in docs if not d.is_open]
    if closed:
        res.customer_id = doc_cust
        res.status, res.confidence, res.exception_type = EXCEPTION, 0.0, "DUPLICATE_PAYMENT"
        for d in closed:
            res.evidence.append(
                f"{d.doc_id} for {fmt(d.original_amount)} was already paid on {d.closed_date} "
                f"(ref {d.closed_by_ref})"
            )
        res.options.append(_hold(dep, doc_cust))
        others = _open_docs(doc_cust, inputs)
        if others:
            apps, _ = _spread(dep.amount, others)
            res.options.append(
                Option(
                    "APPLY_TO_OLDEST_OPEN",
                    "Apply the payment to the customer's oldest open items instead ("
                    + ", ".join(f"{d} {fmt(a)}" for d, a in apps)
                    + ")",
                    Plan(dep.amount, doc_cust, apps),
                )
            )
        return res

    payer_cust = res.customer_id
    if payer_cust and payer_cust != doc_cust:
        rel = related(payer_cust, doc_cust, inputs.customers)
        res.status, res.confidence, res.exception_type = EXCEPTION, 0.0, "PAYER_MISMATCH"
        payer_name = inputs.customers[payer_cust].name
        doc_name = inputs.customers[doc_cust].name
        res.evidence.append(
            f"Payer resolves to {payer_name} ({payer_cust}); the referenced item belongs to "
            f"{doc_name} ({doc_cust})"
        )
        res.evidence.append(rel or "No parent/subsidiary relationship in the customer master")
        apps, left = _spread(dep.amount, docs)
        ref_label = "Apply to the referenced item(s)" + (
            f", leaving {fmt(sum((r for _, r in _residuals(apps, inputs.docs)), ZERO))} open"
            if _residuals(apps, inputs.docs)
            else ""
        )
        if left == 0:
            res.options.append(
                Option("APPLY_TO_REFERENCED_DOC", ref_label, Plan(dep.amount, doc_cust, apps))
            )
        for own in _order(_open_docs(payer_cust, inputs)):
            if own.open_amount == dep.amount:
                res.evidence.append(
                    f"Payer's own open item {own.doc_id} (due {own.due_date}) equals the "
                    f"deposit of {fmt(dep.amount)}"
                )
                res.options.append(
                    Option(
                        f"APPLY_TO_PAYER_DOC:{own.doc_id}",
                        f"Apply to the payer's own open item {own.doc_id}",
                        Plan(dep.amount, payer_cust, [(own.doc_id, own.open_amount)]),
                    )
                )
        res.options.append(_hold(dep, ""))
        res.customer_id = doc_cust
        return res

    res.customer_id = doc_cust
    total_open = sum((d.open_amount for d in docs), ZERO)
    if total_open == dep.amount:
        res.status, res.confidence = AUTO, 0.99
        res.plan = _full_plan(dep, doc_cust, docs)
        return res
    if total_open > dep.amount:
        short = total_open - dep.amount
        auto = _shortfall_auto(dep, doc_cust, docs, short, cfg)
        if auto:
            res.plan, res.rule = auto
            res.status, res.confidence = AUTO, 0.95
            res.evidence.append(f"Shortfall of {fmt(short)} is within policy ({res.rule})")
            return res
        apps, _ = _spread(dep.amount, docs)
        deduction = _has_deduction_words(dep.remittance_text, cfg)
        return _shortfall_exception(res, apps, inputs, cfg, deduction, dep.remittance_text)
    return _overpayment_exception(res, docs, inputs, cfg)


def _match_amount(res: Result, inputs: Inputs, cfg: Config) -> Result:
    dep = res.deposit
    cust = res.customer_id
    docs = _open_docs(cust, inputs)
    combos = _combos(dep.amount, docs, cfg)
    name = inputs.customers[cust].name
    fuzzy = res.name_score < cfg.name_auto_min

    if fuzzy:
        res.rule = "FUZZY_CUSTOMER"
        res.status, res.confidence, res.exception_type = EXCEPTION, 0.0, "LOW_CONFIDENCE_CUSTOMER"
        res.evidence.append(
            f"Payer '{dep.payer_name}' is not a known name; closest customer is {name} "
            f"({cust}) at a name score of {res.name_score:.2f}"
        )
        if len(combos) == 1:
            docs_txt = ", ".join(d.doc_id for d in combos[0])
            res.evidence.append(f"Deposit equals the open balance of {name}'s {docs_txt}")
            res.options.append(
                Option(
                    "APPLY_TO_CANDIDATE",
                    f"Treat the payer as {name} and apply to {docs_txt}",
                    _full_plan(dep, cust, combos[0]),
                )
            )
        else:
            res.evidence.append(f"Deposit does not equal any open item or combination for {name}")
            res.options.append(
                Option(
                    "ON_ACCOUNT_TO_CANDIDATE",
                    f"Treat the payer as {name} and hold the deposit on account",
                    Plan(dep.amount, cust, on_account=dep.amount),
                )
            )
        res.options.append(_hold(dep, ""))
        return res

    if len(combos) == 1:
        res.rule = "AMOUNT_MATCH" if len(combos[0]) == 1 else "MULTI_INVOICE_SUM"
        res.status = AUTO
        res.confidence = round((0.97 if len(combos[0]) == 1 else 0.93) * res.name_score, 2)
        res.plan = _full_plan(dep, cust, combos[0])
        res.evidence.append(
            f"Deposit equals the open balance of {', '.join(d.doc_id for d in combos[0])}; "
            "no other open item or combination matches"
        )
        return res

    if len(combos) > 1:
        res.rule = "MULTI_INVOICE_SUM"
        res.status, res.confidence, res.exception_type = EXCEPTION, 0.0, "AMBIGUOUS_MATCH"
        res.evidence.append(
            f"{len(combos)} different sets of {name}'s open items sum to the deposit"
        )
        for i, combo in enumerate(sorted(combos, key=lambda c: [d.doc_id for d in c]), 1):
            desc = ", ".join(f"{d.doc_id} (dated {d.doc_date}, due {d.due_date})" for d in combo)
            res.options.append(
                Option(f"COMBO_{i}", f"Apply to {desc}", _full_plan(dep, cust, combo))
            )
        res.options.append(_hold(dep, cust))
        return res

    # No exact match: a single item within tolerance?
    for d in _order(docs):
        if d.open_amount > dep.amount:
            auto = _shortfall_auto(dep, cust, [d], d.open_amount - dep.amount, cfg)
            if auto:
                res.plan, res.rule = auto
                res.status, res.confidence = AUTO, round(0.95 * res.name_score, 2)
                res.evidence.append(f"Deposit is within policy tolerance of {d.doc_id}")
                return res

    res.rule = "NO_AMOUNT_MATCH"
    res.status, res.confidence, res.exception_type = EXCEPTION, 0.0, "UNMATCHED_AMOUNT"
    res.evidence.append(f"No open item or combination for {name} equals {fmt(dep.amount)}")
    if docs:
        apps, left = _spread(dep.amount, docs)
        res.options.append(
            Option(
                "APPLY_OLDEST_FIRST",
                "Apply oldest-first across open items"
                + (f", {fmt(left)} left unapplied" if left else ""),
                Plan(dep.amount, cust, apps),
            )
        )
    res.options.append(
        Option(
            "ON_ACCOUNT_CREDIT",
            "Hold the deposit as an on-account credit for the customer",
            Plan(dep.amount, cust, on_account=dep.amount),
        )
    )
    res.options.append(_hold(dep, cust))
    return res


def match_deposit(dep: Deposit, inputs: Inputs, cfg: Config) -> Result:
    res = Result(deposit=dep, status="", rule="", confidence=0.0)
    cust, score, cand, cand_score = resolve_payer(dep.payer_name, inputs.customers)
    if cust:
        res.customer_id, res.name_score = cust, score

    # 1. Structured remittance advice (lockbox / EDI 820)
    if dep.bank_ref in inputs.remittances:
        return _finalize(_match_remittance(res, inputs, cfg), cfg)

    # 2. Document references in the free-text remittance
    refs = [f"{m.group(1).upper()}-{m.group(2)}" for m in REF.finditer(dep.remittance_text)]
    refs = list(dict.fromkeys(refs))
    found = [inputs.docs[r] for r in refs if r in inputs.docs]
    unknown = [r for r in refs if r not in inputs.docs]
    if unknown:
        res.evidence.append(f"Reference(s) not found in AR: {', '.join(unknown)}")
    if found and len({d.customer_id for d in found}) == 1:
        return _finalize(_match_reference(res, found, inputs, cfg), cfg)

    # 3. Customer by payer name, then amount
    if not cust and cand and cand_score >= cfg.name_fuzzy_min:
        res.customer_id, res.name_score = cand, cand_score
    if not res.customer_id:
        res.rule = "NO_CUSTOMER"
        res.status, res.confidence, res.exception_type = EXCEPTION, 0.0, "UNIDENTIFIED"
        res.evidence.append(
            f"Payer '{dep.payer_name}' does not match any customer"
            + (f" (closest: {inputs.customers[cand].name} at {cand_score:.2f})" if cand else "")
        )
        res.evidence.append("Remittance carries no usable document reference")
        res.options.append(_hold(dep))
        return _finalize(res, cfg)
    return _finalize(_match_amount(res, inputs, cfg), cfg)


def _finalize(res: Result, cfg: Config) -> Result:
    """Demote any AUTO result under the confidence floor to an exception."""
    if res.status == AUTO and res.confidence < cfg.auto_apply_min_confidence:
        assert res.plan is not None
        res.evidence.append(
            f"Confidence {res.confidence:.2f} is below the auto-apply floor "
            f"{cfg.auto_apply_min_confidence:.2f}"
        )
        res.status, res.exception_type = EXCEPTION, "LOW_CONFIDENCE_MATCH"
        res.options = [Option("APPLY_PROPOSED", "Apply as proposed", res.plan), _hold(res.deposit)]
        res.plan = None
    return res


def match_all(inputs: Inputs, cfg: Config) -> list[Result]:
    return [match_deposit(d, inputs, cfg) for d in inputs.deposits]
