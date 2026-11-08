# SUBMISSION CHECKLIST

Deadline: 48 hours from receiving the brief. Budget 2-3 hours of work. Submit one form with name, roll number, branch, chosen problem (Problem 2) and links. Every link must open for anyone with the link.

## Deliverables
- [ ] **Solution doc** - PDF, at most 2 pages (outline below)
- [ ] **Prototype link** - GitHub repo with clear run steps (hosted app optional bonus)
- [ ] **Raw outputs** - the `outputs/run_<...>/` folder, unedited, including failures
- [ ] **Walkthrough video** (optional, recommended) - up to 3 minutes, your own voice

## 2-page solution doc outline
1. **Problem and why** (4-5 lines): everyday legal problems; why deposit + refund; why these two over others (frequency, small amounts, clear forums); arbitration check because buried clauses mislead people.
2. **Assumptions** (bullets): audience (urban, smartphone, English/Hinglish); scope limits; synthetic test data; KB entries need lawyer verification; no OCR; single-session memory.
3. **How it works**: one small diagram (chat, upload, summary, timeline, notice, checks); **what AI does vs what code does** (table from `ARCHITECTURE.md`); model swap by `.env`.
4. **How it avoids invented law**: KB-only rule with ids, citation scan, quote verification, code-based escalation, "I don't know" behaviour.
5. **Scale and cost**: tokens per case (estimate from `meta.json`), free tier for demo, what a paid model would cost per 1,000 cases, how to add states/topics (KB entries + tests), human-in-the-loop (lawyer reviews KB and notices), monitoring (flag counts, drop rates).
6. **Quality results**: the metrics table from the latest `report.md` and **3 honest failures** with causes.
7. **Tools used and where they were wrong**: list tools (DeepSeek in VS Code, the free LLM provider, others) and one concrete example where an AI tool gave wrong output and how you caught it.
8. **Limits and next steps**: what it does not cover; what you would build next.

## Walkthrough video outline (about 3 minutes)
- 0:00-0:20 Problem and scope.
- 0:20-1:30 Live demo: chat a deposit story, upload a sample agreement, show summary with the arbitration card, show timeline with source quotes.
- 1:30-2:15 Safety: show a test where the model tried to cite an unlisted section and it was removed, and an urgent escalation case.
- 2:15-2:45 Model swap: change `.env`, rerun eval, show the report.
- 2:45-3:00 Limits and what is next.

## Repo hygiene before submitting
- [ ] README has run steps that work on a clean machine (`pip install -r requirements.txt`, `.env.example`, `python app.py`).
- [ ] No API keys in the repo or in the git history. `.env` is in `.gitignore`.
- [ ] `outputs/` contains a real, complete eval run with `report.md`.
- [ ] `docs/FAILURES.md` exists with real entries.
- [ ] `kb.json` entries show `verified` honestly (do not set `true` without checking the source).
- [ ] Demo warning about not uploading real documents is visible in the UI.
- [ ] `pytest -q` passes.
- [ ] The app runs on a fresh run of `scripts/run_eval.py` (interviewers may run it on a new input).

## AI usage log (keep as you build; paste highlights into the doc)
| Step | Tool | What I asked | What went wrong | How I caught/fixed it |
|---|---|---|---|---|
| | | | | |
