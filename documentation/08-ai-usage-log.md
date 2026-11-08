# 8. AI usage log

The assignment asks for honesty about AI tools, including where they were wrong.
This log records what was generated with AI assistance and, more usefully, the
defects that were caught afterwards.

## Tools used

| Tool | Role |
|---|---|
| VS Code AI assistant (Copilot-class agent) | Generated the application code, tests and this documentation from the written spec in `../docs/` and `../PROJECT_CONTEXT.md` |
| Groq (OpenAI-compatible) | The runtime model behind the app |
| `uv` | Environment and dependency resolution |
| `pytest` | Test execution |

All legal *content* in the app came from the specification's starter entries and
lives in `kb.json`; no model was used to write legal text, and none of it is
verified yet.

## Where the AI was wrong

These are real defects found by running the code, not hypothetical risks.

| # | Area | What the AI produced | How it was caught | Fix |
|---|---|---|---|---|
| 1 | `checks.scan_citations` | A version that deleted the plain sentence "The exact code is in the agreement", mistaking it for a statute citation, while letting the real case name "Sharma v. Verma" through | Reading regex output against ordinary English sentences | Pattern tightened to title-case Act names; sentence splitter now keeps `v.` attached |
| 2 | Sentence splitting | Split "Sharma v. Verma" into two fragments so the case-name regex never matched | Unit test on an invented case name | `split_sentences()` merges abbreviation-terminated fragments |
| 3 | Escalation keywords | Copied the spec keyword "lock changed" literally, so "my landlord **changed the lock**" did not escalate | Unit test on natural phrasing | Added both word orders |
| 4 | Number check | Regex `\brs\.?\b` never matched "Rs. 95,000", so the unverified-number check silently did nothing | Unit test that expected a flag and got none | Boundary removed from the pattern |
| 5 | `llm.py` | Built the provider client outside the `try` block, so a bad key or base URL escaped as a 500 instead of `llm_unavailable` | Review while writing the failure-mapping test | Client construction moved inside the guard |
| 6 | `llm.py` | Retried every non-429 status three times with 1 s and 2 s sleeps. A retired model id produced an 8-second chat turn ending in "no provider is reachable", with the status code discarded | Live run: `HTTP 404` for `llama-3.3-70b-versatile`, a model Groq had retired | 4xx (except 429) is now non-retryable; status and provider error code are logged |
| 7 | Notice placeholders | Extraction pattern accepted only uppercase, so a real notice containing `[Your Name]` reported 1 of 5 blanks — the UI would have hidden four | Live notice call against Groq | Pattern accepts mixed case and apostrophes; the prompt asks for capitals |
| 8 | Frontend | Rendered model output as plain text, so `1. **Send a Legal Notice:**` appeared with literal asterisks | Browser snapshot after the user reported the chatbot "felt traditional" | Small DOM-only markdown renderer (bold, italic, code, lists); no `innerHTML` |
| 9 | Frontend | All three numbered steps collapsed into one bullet, because the model puts them on a single line | Browser snapshot of a real reply | Renderer splits inline numbered sequences |
| 10 | Frontend | A long source chip forced a horizontal scrollbar, and its trailing "." wrapped to its own line | Measured `scrollWidth` vs `clientWidth` in the page | Chip can wrap; punctuation moved inside the chip |
| 11 | Frontend | New suggestion chips threw a `TypeError` when the HTML document was served from cache, producing a false "Could not start a session" error | Browser run showed the error box while a session had clearly succeeded | Container created on demand; static files now sent with `no-cache` |
| 12 | Prompting | Relying on the prompt for "at most one question" did not hold — a live reply asked two questions and gave no steps | Live run on a refund case | Prompt rewritten value-first, plus deterministic `limit_questions()` in code |
| 13 | Documentation | (This file) an earlier draft of the run instructions assumed Python was on `PATH`; the build machine had none | Running the commands | Instructions use `uv run`, which provisions its own interpreter |

## What the AI was good at

- Producing complete, internally consistent modules from a detailed spec.
- Writing the deterministic checks (quote verification, date parsing, escalation)
  accurately once the requirements were precise.
- Generating a broad test suite, which is what caught most of the defects above.

## What it needed a human for

- Noticing that the *product behaviour* was wrong even when the code was correct —
  the "feels like a traditional chatbot" judgement came from the user, not the
  tool.
- Deciding that placeholders should be detected case-insensitively rather than
  trusting the model to follow formatting instructions.
- Insisting that evaluation failures be kept in `outputs/` rather than cleaned up.

## Policy followed

- No API key is written into code, tests or documentation; `.env` is gitignored and
  must not be shipped in a zip.
- Message and document text are never logged; logs carry identifiers, timings and
  token counts only.
- No legal text was generated by a model. Legal content is confined to `kb.json`
  and is marked unverified until a human checks it.
