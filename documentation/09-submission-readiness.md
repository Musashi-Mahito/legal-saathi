# 9. Submission readiness

This maps every item in [`../docs/SUBMISSION_CHECKLIST.md`](../docs/SUBMISSION_CHECKLIST.md)
to its actual status. Nothing here is marked done unless it was verified by running
something.

Status legend: **Done** (verified) · **Action needed** (cannot be produced by the
build itself) · **Partial** (exists, with a stated limitation).

---

## Deliverables

| Item | Status | Where |
|---|---|---|
| Solution doc, PDF, at most 2 pages | **Done** | [`legal-saathi-solution-doc.pdf`](legal-saathi-solution-doc.pdf) (source: [`solution-doc-2page.md`](solution-doc-2page.md)) |
| Prototype link (GitHub repo) | **Action needed** | This folder is not a git repository yet. `git init && git add . && git commit` is safe: `.gitignore` already excludes `.env`, `.venv/` and `jobs/`. Then push and paste the URL into the submission form. |
| Raw outputs folder, unedited, including failures | **Done** | [`../outputs/run_20261108_1708/`](../outputs/run_20261108_1708/) — `report.md` plus 12 case folders with `chat_turns.json`, `summary.json`, `timeline.json`, `notice.md`, `meta.json`. Failures are still in the table. |
| Walkthrough video (optional) | **Action needed** | Needs your voice. A timed script is in [`walkthrough-video-script.md`](walkthrough-video-script.md) and matches the checklist's 0:00–3:00 outline. |

## The 8-point solution doc

Every point is covered in [`solution-doc-2page.md`](solution-doc-2page.md):

| Checklist point | Section in the doc |
|---|---|
| 1. Problem and why | "Problem" + "Why these two" |
| 2. Assumptions | "Assumptions" |
| 3. How it works (diagram, AI vs code, model swap) | "How it works" (flow + table + `.env` note) |
| 4. How it avoids invented law | "Why it cannot invent law" (4 mechanisms) |
| 5. Scale and cost | "Scale and cost" — **measured** tokens, cost formula, KB growth, monitoring |
| 6. Quality results + 3 honest failures | "Results" (metrics table + 3 named failures) |
| 7. Tools used and where they were wrong | "Tools and where they were wrong" |
| 8. Limits and next steps | "Limits and next" |

## Repo hygiene

| Item | Status | Evidence |
|---|---|---|
| README run steps work on a clean machine | **Done** | Verified by copying the project **without `.venv`** to a fresh folder: `uv run pytest -q` → 143 passed, app answered. See [05-running-and-portability.md](05-running-and-portability.md). Note: the checklist says `pip install -r requirements.txt`; `requirements.txt` is still present and works, and `uv run` is the preferred path. |
| No API keys in the repo; `.env` gitignored | **Done (repo) / ⚠️ see note** | `.gitignore` contains `.env`. **However the working copy's `.env` currently holds a real Groq key.** Do not zip or commit this folder as-is. The submission zip excludes `.env` and ships a keyless copy. If that key was ever shared, rotate it. |
| `outputs/` has a complete eval run with `report.md` | **Partial** | Present and complete, but produced with the **offline provider**, so domain accuracy reads 7/12 because the fixture always answers as a deposit case. Re-run with a key for real numbers: `uv run python scripts/run_eval.py --provider groq`. |
| `docs/FAILURES.md` has real entries | **Done** | 8 numbered defects with cause and fix, plus the AI-assistant mistake table. All were found by running the code. |
| `kb.json` shows `verified` honestly | **Done** | All 15 entries are `false`; none were flipped to look better. |
| Demo warning visible in the UI | **Done** | Amber banner on the Documents tab: *"Demo only: please upload sample or redacted documents, not real personal papers."* |
| `pytest -q` passes | **Done** | 143 passed, offline, no key. |
| App runs on a fresh `scripts/run_eval.py` | **Done** | Regenerated `run_20261108_1708` from scratch during this submission pass. |

## AI usage log

The checklist asks for `Step | Tool | What I asked | What went wrong | How I caught/fixed it`.
[08-ai-usage-log.md](08-ai-usage-log.md) holds 13 rows in that spirit (area, what the
tool produced, how it was caught, the fix), plus a "what it was good at" and a
policy section. Paste the first 5–6 rows into the submission form.

---

## What still has to happen before you submit

1. **Rotate the Groq key** if this folder was shared anywhere, then delete the key
   from `.env` or keep `.env` out of every upload.
2. **`git init` + push** to get the prototype link.
3. **Record the 3-minute video** using the script in the solution doc.
4. **Optional but recommended:** run `uv run python scripts/run_eval.py --provider groq`
   once so `outputs/` shows real-model metrics rather than fixture metrics, and
   replace the table in point 6 of the solution doc with those numbers.

## Honest gaps a reviewer may notice

- The evaluation numbers are fixture-driven, not model-driven (explained in the run
  folder's `report.md` itself, not hidden).
- Every KB entry is unverified, so answers hedge. That is the correct state, but it
  is the first thing a reviewer will ask about.
- No OCR and no voice: scanned agreements are rejected, not guessed.
- Sessions are in-memory only; there is no login or history.
