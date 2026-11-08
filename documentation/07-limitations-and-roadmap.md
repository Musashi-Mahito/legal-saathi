# 7. Limitations and roadmap

## Limitations of the current build

### Knowledge, not language, is the bottleneck

Every entry in `kb.json` is `verified: false`. The prompt therefore requires the
assistant to add "(please confirm this with a lawyer or the official source)" to
almost every answer. This is deliberate — a human must read the Act text before a
`verified: true` is honest — but it makes the assistant sound hedged. The single
highest-value next step is a lawyer reviewing those 15 entries.

The KB is also **small and central**. Deposit law varies by state; the app says so
rather than pretending otherwise. A `state` field per entry is the natural
extension.

### What the app cannot do

| Limitation | Consequence |
|---|---|
| No OCR | Scanned PDFs and photos are rejected with a clear message, never guessed at |
| No voice | Typing only |
| Session-scoped memory | Restarting the server loses the conversation; there is no login or history |
| Single worker | In-memory sessions do not survive a multi-process deployment |
| No court filing, no e-filing integration | The draft notice is text the user sends themselves |
| Best-effort Hindi | Devanagari is handled, but quality is model-dependent and untested at scale |
| No appeals, execution or enforcement guidance | Ends at "file the complaint / send the notice" |
| Amounts and dates can enter the case file wrongly | The case file is model-filled; the UI shows it for correction but does not validate it against the user's words |

### Known failure modes

- **Time-bar detection needs a date.** If the model does not extract
  `cause_of_action_date`, the 24-month rule cannot fire.
- **Keyword escalation over-triggers.** "Police" in an unrelated sentence raises
  the level. Over-escalation is the safe direction, but it is a known cost.
- **Injection defence is partly phrase-based.** Regex catches the obvious
  attempts; the real protection is that injected instructions still have to pass
  schema validation, citation scanning and quote verification.
- **Prompt behaviour drifts.** The single-question rule had to be enforced in code
  because the prompt alone was not reliable. Expect more of this over time.
- **Free tiers throttle.** `429` back-offs make some requests slow. Sequential
  chunk processing keeps within limits at the cost of latency.

---

## Roadmap

### Next (days of work)

1. **Human-verify the KB.** Read each entry against `indiacode.nic.in` and the
   official consumer-affairs pages; fill `source_url`, set `last_verified`, then
   `verified: true`. This alone changes the product's tone.
2. **Add state-level deposit entries** using a `state` field, starting with the
   metros (Maharashtra, Karnataka, Delhi, Tamil Nadu).
3. **Validate case-file facts against the user's words.** Every merged amount and
   date should have to appear in the message that "provided" it; otherwise mark it
   as unconfirmed in the UI.
4. **Real-provider evaluation in CI.** Run `scripts/run_eval.py --provider groq`
   on a schedule and track the metrics table over time.

### Later

5. **Streaming replies**, once the validation pipeline can be applied
   incrementally. Today the reply is schema-validated, citation-scanned and
   question-limited *before* it is shown; streaming would need each chunk to be
   validated, or the answer would be streamed unverified.
6. **A verified-notice path.** Generate the notice, let a partner lawyer review it
   asynchronously, then release it — turning a draft into something a person can
   actually send.
7. **Marathi and Bengali**, following the same KB-then-prompts order.
8. **Voice input** for low-literacy users, with the transcript shown for
   confirmation before any advice is given.
9. **Retrieval instead of a small file.** Once the KB grows past a few hundred
   entries, select entries by embedding similarity rather than domain filtering —
   with the same allowlist guarantee.

### What I would not build

- **Outcome prediction** ("you will win"). It is unknowable and it is the surest
  way to harm someone who then misses a deadline.
- **Auto-filing to a court or commission portal.** Too much liability for a
  document generator.
- **Silent knowledge-base growth by scraping.** Unverified legal text scraped from
  the internet is exactly the failure this architecture exists to prevent.
