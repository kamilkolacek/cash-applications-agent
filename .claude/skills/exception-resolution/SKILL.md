---
name: exception-resolution
description: Playbook for recommending a resolution to each cash application exception type (short-pay, partial, overpayment, ambiguous match, unidentified cash, low-confidence customer, payer mismatch, duplicate payment). Use when writing resolutions.json, in /apply-cash and /exceptions.
---

# Exception resolution playbook

You choose one of the options the engine offered. You cannot add an option, change an
amount, or split a deposit differently. When no option is supported by the evidence,
choose `HOLD_UNAPPLIED`: cash on the wrong customer is harder to unwind than cash left
unapplied for a day.

## Principles

1. **Evidence over convenience.** A recommendation must rest on something in the record:
   a document reference, an exact amount, a date, a customer-master relationship, words
   in the remittance. Name it in the rationale.
2. **Exact beats close.** An exact amount match to a specific open item is strong
   evidence. A similar name alone is weak evidence.
3. **The customer's words count.** "Installment 1 of 2", "less makegood", "Oct services"
   tell you their intent. Follow it unless the record contradicts it.
4. **No write-offs beyond authority.** Agent authority is $10.00. A larger shortfall is a
   deduction to validate, an open balance to collect, or a hold.
5. **Every hold gets an owner and a next step.**

## By exception type

### SHORT_PAY (customer took a deduction)
- Remittance gives a reason (makegood, under-delivery, pricing, damaged, co-op):
  `APPLY_AND_RECLASS_DEDUCTION`. The deduction moves to 120300 so AR aging stays clean and
  the owning team validates it. Owner: Ad Sales for advertising makegoods and delivery
  claims; Partner Finance for distribution and licensing.
- No stated reason: prefer `APPLY_LEAVE_OPEN` and ask the customer.
- Rationale names the reason code or words and the deduction amount.

### PARTIAL_PAYMENT
- Customer says installment / partial / payment plan, or the remainder is plainly still
  owed: `APPLY_PARTIAL_LEAVE_OPEN`. Follow-up: confirm the plan exists and the next due date.
- Choose `HOLD_UNAPPLIED` only if the referenced item is doubtful.

### OVERPAYMENT
- The excess equals another open item for the same customer exactly:
  `APPLY_EXCESS:<doc>`. Customers often pay two invoices and reference one.
- Otherwise `APPLY_EXCESS_ON_ACCOUNT`, and follow up to ask whether they want a refund or a
  credit.

### AMBIGUOUS_MATCH (more than one set of open items equals the deposit)
- Use the remittance text first: a month, a campaign, a PO.
- Then the customer's pattern: pay oldest first, past-due before current.
- If nothing distinguishes the sets, `HOLD_UNAPPLIED` and ask for remittance detail.

### UNIDENTIFIED
- `HOLD_UNAPPLIED`. Follow-up for AR: trace the originating account with the bank, check
  for a new customer or an unsigned deal, check recent customer name changes. Treasury
  should know the amount is unidentified.

### LOW_CONFIDENCE_CUSTOMER
- Name is a plausible abbreviation or misspelling **and** the deposit exactly equals an
  open item of that customer: `APPLY_TO_CANDIDATE`. Follow-up: add the bank name as an
  alias in the customer master.
- Name is similar but different words (Northside vs Northstar), or the amount ties to
  nothing: `HOLD_UNAPPLIED`. Do not put cash on account for a customer you have not
  identified.

### PAYER_MISMATCH (payer is one customer, the reference belongs to another)
- Customer master shows a parent/subsidiary or shared parent and the amount fits:
  `APPLY_TO_REFERENCED_DOC`. Paying on behalf of an affiliate is normal.
- No relationship, but the payer has its own open item equal to the deposit and the
  reference looks like a keying error (transposed or swapped digits):
  `APPLY_TO_PAYER_DOC:<doc>`. Say what the error looks like. Follow-up: confirm with the payer.
- No relationship and no such match: `HOLD_UNAPPLIED`. Never apply one customer's cash to
  an unrelated customer's invoice.

### DUPLICATE_PAYMENT (referenced item is already paid)
- `HOLD_UNAPPLIED`. Do not move the cash onto other open items to make it disappear.
  Follow-up for AR: contact the customer to confirm the duplicate and ask for refund or
  credit instructions. Cite when and how the item was already paid.

### UNMATCHED_AMOUNT / REMITTANCE_MISMATCH / LOW_CONFIDENCE_MATCH
- Prefer `HOLD_UNAPPLIED` unless the evidence clearly supports one option; say what
  information would settle it.

## Writing the rationale

Two to four sentences. Cite the evidence with figures exactly as they appear in
`exceptions.json`. State why the other options are worse when that is not obvious.
`follow_up` is a concrete next action for a person. `owner` is one of AR, Ad Sales,
Partner Finance, Treasury.
