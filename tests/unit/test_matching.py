from decimal import Decimal

from cashapp.customers import normalize, resolve_payer
from cashapp.matching import AUTO, EXCEPTION, REF, match_all
from cashapp.money import D, fmt


def test_money_parsing_and_format():
    assert D("1,234.5") == Decimal("1234.50")
    assert fmt(D("-6200")) == "-$6,200.00"


def test_reference_regex_variants():
    text = "PMT INV-24161, inv 24162 and CM#24123 /INV/INV-24164"
    refs = {f"{m.group(1).upper()}-{m.group(2)}" for m in REF.finditer(text)}
    assert refs == {"INV-24161", "INV-24162", "CM-24123", "INV-24164"}


def test_normalize_strips_suffixes_and_punctuation():
    assert normalize("Ember & Oak Retail, Inc.") == "EMBER OAK RETAIL"


def test_payer_resolution(inputs):
    cust, score, *_ = resolve_payer("KESTREL FOODS INC", inputs.customers)
    assert (cust, score) == ("C001", 1.0)
    cust, score, cand, cand_score = resolve_payer("NRTHSTR MEDIA GRP", inputs.customers)
    assert cust is None and cand == "C003" and 0.70 <= cand_score < 0.92
    # Shared trailing word is not enough: the first word must also be close.
    _, _, cand, _ = resolve_payer("J SMITH HOLDINGS LLC", inputs.customers)
    assert cand is None


def test_every_plan_accounts_for_the_whole_deposit(inputs, cfg):
    for r in match_all(inputs, cfg):
        plans = [r.plan] if r.status == AUTO else [o.plan for o in r.options]
        assert plans and all(p is not None for p in plans)
        for p in plans:
            assert p.applied + p.on_account + p.unapplied == r.deposit.amount
            assert p.unapplied >= 0


def test_exceptions_always_offer_a_hold(inputs, cfg):
    for r in match_all(inputs, cfg):
        if r.status == EXCEPTION:
            assert "HOLD_UNAPPLIED" in {o.option_id for o in r.options}


def test_no_writeoff_option_beyond_authority(inputs, cfg):
    for r in match_all(inputs, cfg):
        plans = [r.plan] if r.status == AUTO else [o.plan for o in r.options]
        for p in plans:
            for a in p.adjustments:
                if a.kind == "SMALL_BALANCE":
                    assert a.amount <= cfg.small_balance_max
                if a.kind == "BANK_FEE":
                    assert a.amount <= cfg.bank_fee_max_wire


def test_auto_matches_meet_confidence_floor(inputs, cfg):
    for r in match_all(inputs, cfg):
        if r.status == AUTO:
            assert r.confidence >= cfg.auto_apply_min_confidence
