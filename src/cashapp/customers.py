"""Resolve a bank payer name to a customer in the master file."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from cashapp.data import Customer

HEAD_MIN = 0.6
SUFFIXES = {"INC", "LLC", "LTD", "CO", "CORP", "CORPORATION", "PLC", "GMBH", "AB", "THE", "SA"}


def normalize(name: str) -> str:
    words = re.sub(r"[^A-Z0-9 ]", " ", name.upper()).split()
    return " ".join(w for w in words if w not in SUFFIXES)


def resolve_payer(
    payer_name: str, customers: dict[str, Customer]
) -> tuple[str | None, float, str | None, float]:
    """Return (customer_id, score, best_candidate_id, best_candidate_score).

    Exact alias or name match scores 1.0. Otherwise the best fuzzy score is returned as a
    candidate; the caller decides whether that score is good enough to use.
    """
    target = normalize(payer_name)
    head = target.split()[0] if target else ""
    best_id, best = None, 0.0
    for c in customers.values():
        names = {normalize(c.name), *(normalize(a) for a in c.bank_aliases)}
        if target in names:
            return c.customer_id, 1.0, c.customer_id, 1.0
        for n in names:
            # The distinctive first word must be close too: "J SMITH HOLDINGS" is not
            # "ORBIT HOLDINGS" just because the endings match.
            if SequenceMatcher(None, head, n.split()[0]).ratio() < HEAD_MIN:
                continue
            score = SequenceMatcher(None, target, n).ratio()
            if score > best:
                best_id, best = c.customer_id, score
    return None, 0.0, best_id, round(best, 3)


def related(a: str, b: str, customers: dict[str, Customer]) -> str | None:
    """Describe a parent/subsidiary/sibling relationship between two customers, if any."""
    ca, cb = customers.get(a), customers.get(b)
    if not ca or not cb:
        return None
    if cb.parent_id == a:
        return f"{ca.name} is the parent of {cb.name} in the customer master"
    if ca.parent_id == b:
        return f"{cb.name} is the parent of {ca.name} in the customer master"
    if ca.parent_id and ca.parent_id == cb.parent_id:
        return f"{ca.name} and {cb.name} share parent {ca.parent_id} in the customer master"
    return None
