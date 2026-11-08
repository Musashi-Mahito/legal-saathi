# Walkthrough video script (3 minutes)

Matches the outline in [`../docs/SUBMISSION_CHECKLIST.md`](../docs/SUBMISSION_CHECKLIST.md).
Record with the app already running (`uv run app.py`) and a sample document ready
in `tests/docs/rental_agreement_with_arbitration.txt`.

> Keep the browser window clean: no personal tabs, no API keys visible on screen.
> When you show `.env`, blur or scroll past the `*_API_KEY` lines.

---

## 0:00 - 0:20 · Problem and scope

**Say:** "A tenant's deposit is withheld, or a refund never arrives. The amount is
too small for a lawyer, and the person doesn't know which forum, what deadline, or
what to do next. Legal Saathi handles exactly two problems - tenant deposit and
consumer refund - and refuses everything else honestly."

**Show:** the landing page and the footer disclaimer.

## 0:20 - 1:30 · Live demo

| Time | Do | Point out |
|---|---|---|
| 0:20 | Click the example chip "My landlord is not returning my Rs 60,000 security deposit" | The reply gives three numbered steps *before* asking anything, and ends with exactly one question |
| 0:40 | Point at the source chips | "Every legal claim is tagged to a knowledge-base entry. These are dashed because they are not human-verified yet." |
| 0:55 | Documents tab → upload `rental_agreement_with_arbitration.txt` | "PDF, DOCX or TXT, parsed in memory, never written to disk." |
| 1:05 | Summary tab → Summarize | **The arbitration card**: found, quote shown, plain explanation, KB ids |
| 1:20 | Timeline tab → Build timeline | Dated events with source quotes; undated items separated; "N items removed because they could not be verified" |

## 1:30 - 2:15 · Safety

- **Unlisted citation is removed.** Open a terminal and run:
  `uv run python -c "import checks; print(checks.scan_citations('File under Section 420 IPC. Keep your receipts.', set())[0])"`
  **Say:** "The invented section is deleted and the user is told a part was removed. This runs on every reply."
- **Fabricated quote is dropped.** Show `outputs/run_*/D2/summary.json` or run the
  quote-verification test:
  `uv run pytest tests/test_checks.py -q -k fabricated`
- **Urgent escalation.** In chat, type: *"My landlord changed the lock and is
  threatening to call the police."* **Say:** "The red banner is decided by code,
  not by the model. The model can raise the level, never lower it."

## 2:15 - 2:45 · Model swap and evaluation

- Show `.env`, and change `LLM_PROVIDER_ORDER=fake` → `groq` (or the reverse).
  **Say:** "Swapping the model is an `.env` change. `llm.py` is the only file that
  knows a provider exists."
- Open `outputs/run_20261108_1708/report.md`. **Say:** "Raw model outputs are kept
  unedited, including the failures. These particular numbers are from the offline
  provider, which always answers as a deposit case - so the refund cases fail
  domain by construction. It proves the harness, not the model."

## 2:45 - 3:00 · Limits and next

**Say:** "No OCR, no voice, no login. Every knowledge-base entry is unverified, so
the app hedges - that is the correct state until a lawyer checks them. Next step is
getting those 15 entries verified, then state-level deposit rules."

---

## Checklist before you upload

- [ ] `.env` with the real key is not visible at any point
- [ ] No real personal documents on screen (use `tests/docs/*.txt`)
- [ ] The arbitration card is visible at least once
- [ ] The urgent banner is visible at least once
- [ ] The "removed because it could not be verified" line is visible at least once
- [ ] Under 3 minutes
