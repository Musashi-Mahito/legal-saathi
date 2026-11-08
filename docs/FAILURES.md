# Honest failure log

Real problems found while building and evaluating this project. Nothing here is
cosmetic: each entry is a case where the system - or the person building it -
was wrong.

## 1. Safety check failures found by unit tests

| # | Where | What went wrong | Why | Fix / status |
|---|---|---|---|---|
| 1 | `checks.scan_citations` | The case name "Sharma v. Verma" survived the scan. | The sentence splitter treated "v." as a sentence end, so the fragment "Sharma v." and "Verma." never matched the case-name pattern. | Fixed: `split_sentences()` now merges fragments whose last word is an abbreviation (`v.`, `vs.`, `Rs.`, initials). Regression test: `test_section_420_and_unlisted_case_are_removed`. |
| 2 | `checks.escalate` | "My landlord changed the lock" did **not** escalate to urgent. | The keyword list from the spec contains "lock changed", but the natural phrasing puts the words the other way round. | Fixed: added "changed the lock" and "changed lock" keywords. Test: `test_urgent_keywords_raise_level`. |
| 3 | `checks.warn_unverified_numbers` | "Rs. 95,000" was never checked at all. | The regex `\brs\.?\b` required a word boundary after the optional dot, which never matches in "Rs. 95,000". The check silently passed. | Fixed: `RUPEE_RE` no longer requires the trailing boundary. Test: `test_unverified_numbers_flagged`. |
| 4 | `checks.scan_injection` | "disregard the rules above" was not detected. | The pattern only accepted "previous/above/prior" immediately after "disregard". | Fixed: the pattern now allows up to three words before the target noun. Test: `test_injection_phrases_detected`. |
| 5 | `llm._call_provider` | An exception raised while building the provider client escaped the error mapping. | `openai.OpenAI(...)` was created outside the `try` block. A bad key or bad base URL would have reached the global handler as a 500 instead of `llm_unavailable`. | Fixed: client creation moved inside the guarded block. Test: `test_api_key_never_appears_in_errors`. |

## 2. AI-assistant mistakes caught during the build

| Step | Tool | What I asked | What went wrong | How I caught/fixed it |
|---|---|---|---|---|
| Safety checks | AI coding assistant | Implement `scan_citations` per `docs/SAFETY_AND_CHECKS.md` | The first version of `ACT_RE` matched any 4+ letter word followed by "code", so the sentence "The exact code is in the agreement" was deleted as if it cited a statute. | Caught by reading the regex output on a plain-English sentence; the pattern now requires title-case Act names, not a case-insensitive word scan. |
| Eval harness | AI coding assistant | Write `scripts/run_eval.py` that never edits model output | The first draft rewrote `notice.md` from the JSON field after stripping it, which is a silent edit of the model's output. | Caught in review; the harness now writes the raw response objects to disk before any evaluation, and `notice.md` is written verbatim. |

## 5. Failures found during the first real-provider run

| # | Where | What went wrong | Why | Fix / status |
|---|---|---|---|---|
| 6 | `.env` / provider config | Every chat returned "I'm having trouble right now". The server log showed `POST https://api.groq.com/openai/v1/chat/completions "HTTP/1.1 404 Not Found"`. | The provider had **retired** `llama-3.3-70b-versatile`; the key and base URL were fine. A 404 from an OpenAI-compatible endpoint is usually a dead model id, not a broken client. | Fixed: model set to one the key can actually use (checked with `GET /models`). Documented in `docs/LLM_LAYER.md`. |
| 7 | `llm.complete` | That 404 was retried 3 times with 1s + 2s sleeps, so a single chat turn took 7.9 s and then reported only "no provider is reachable". | `_call_provider` mapped every non-429 status to a retryable `LLMUnavailable` and dropped the status code. | Fixed: 4xx (except 429) is non-retryable, the provider is skipped immediately, and `status` + provider error `code` are logged. Tests: `test_configuration_error_is_not_retried`, `test_error_code_extraction`. |
| 8 | `notice_service` | A live notice used `[Your Name]`, `[Landlord's Address]`, `[Property Address]`; only 1 of 5 blanks was reported in `missing_placeholders`. | The extraction pattern was uppercase-only (`\[[A-Z0-9 _\-/]+\]`), so Title Case placeholders were invisible. The UI would have highlighted one blank and hidden four. | Fixed: pattern accepts mixed case and apostrophes, still skipping `[KB:id]` and markdown links; the prompt now asks for capitals too. Test: `test_placeholder_extraction_handles_mixed_case`. |

## 6. Known limitations that show up in evaluation

| Case | What goes wrong | Why | Status |
|---|---|---|---|
| R1, R2, R3, R4, E2 | With the offline fake provider, every reply is the canned deposit answer, so refund cases fail `domain`, and the Hinglish case fails `reply_language`. | The fake provider is a fixed fixture; it exists so tests and CI run without an API key. | Expected. Use a real key (`python scripts/run_eval.py --provider groq`) for meaningful numbers. |
| E4 | The fake provider answers with `domain: "deposit"` instead of `unknown`. | Same fixture limitation. | Expected with the fake provider. |
| R4 | The two-year time bar is only escalated when the model fills `facts.common.cause_of_action_date`. | The code rule is deterministic but needs the fact; the model decides the date. | Known limitation: a missing date means no time-bar warning. Prompt wording is the only lever. |
| E3 | Injection detection relies on phrase matching. | A carefully reworded instruction will not match the patterns. | Partly mitigated: citation scan, quote verification and schema validation still run on the model output. |

## 4. Environment notes

- The machine used for this build had no Python on `PATH`; the app runs through
  `uv run app.py`, which provisions `.venv` from `uv.lock`.
- The committed evaluation run in `outputs/run_20261108_1324/` was produced with
  `LLM_PROVIDER_ORDER=fake`, before a provider key was available. The `meta.json`
  files record that honestly. A real run is
  `uv run python scripts/run_eval.py --provider groq`.
- Free tiers are tight: a live run hit `429` twice, and one timeline request took
  52 s while the SDK backed off. `scripts/run_eval.py` processes calls sequentially
  for the same reason.
