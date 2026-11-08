# FRONTEND SPEC

Single page: `templates/index.html`, `static/app.js`, `static/style.css`. No framework, no build step, no external CDN scripts. Mobile-friendly (many users will be on a phone).

## Layout
- **Header:** app name, one-line tagline, language hint ("Write in English, Hindi or Hinglish").
- **Escalation banner** (hidden unless `escalation.level != "none"`): amber for `advise`, red for `urgent`; lists reasons and resources.
- **Left / main column: Chat**
  - Message list (user right, assistant left), typing indicator, auto-scroll.
  - Input box + Send button (Enter sends, Shift+Enter new line). Disable while waiting.
  - `[KB:id]` tags in replies render as small chips ("Source: <title>"), with an "unverified" style when the KB entry has `verified: false` (fetch from `GET /api/kb`, see below).
- **Right column (tabs): Documents | Summary | Timeline | Notice | Case file**
  - **Documents:** file picker (`.pdf,.docx,.txt`), upload button, list of uploaded files with warnings/flags. Visible warning: "Demo only: please upload sample or redacted documents, not real personal papers."
  - **Summary:** button "Summarize" (per document, dropdown if several). Renders `plain_summary`, parties, amounts, dates, clauses, red flags. A highlighted card **"Arbitration clause"** shows found/not found, the quote and the plain explanation.
  - **Timeline:** button "Build timeline". Vertical list ordered by date: date, event text, confidence badge, source badge (document/chat), and an expandable "Show source quote". Undated items listed below. Show "N items removed because they could not be verified".
  - **Notice:** button "Draft notice" (enabled when domain is deposit/refund). Shows markdown in a `<pre>`-style block, missing placeholders highlighted, "Copy" and "Download .txt" buttons, and the DRAFT warning.
  - **Case file:** read-only readable view of facts, evidence, missing info (what the bot still needs).
- **Footer:** "Legal Saathi gives information, not legal advice. For urgent or high-value matters, consult a lawyer or your District Legal Services Authority."

## Extra endpoint for the UI
`GET /api/kb` returns `[{id, title, verified}]` only (no rules) so the UI can label chips. Add it to `app.py`.

## Behaviour
- On load: `POST /api/session`, keep `session_id` in a JS variable (not localStorage).
- Every request shows a loading state; errors show a dismissible message using the API's `error.message`.
- Never render model output as HTML: set `textContent`, or escape before converting minimal markdown (bold, line breaks, lists).
- Accessible: labels on inputs, buttons reachable by keyboard, sufficient colour contrast, `aria-live="polite"` on the message list.
- Respect light/dark preference with CSS variables and `prefers-color-scheme`.
- Handle `flags`: show small notes for `unverified_reference_removed`, `unverified_number`, `possible_prompt_injection`, `partial_result`, `llm_failure`.

## Not in scope
Login, history across sessions, voice input, streaming tokens (optional later), multi-user.
