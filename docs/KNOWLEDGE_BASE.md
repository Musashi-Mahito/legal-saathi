# KNOWLEDGE BASE (`kb.json`)

## Purpose
The only place legal facts may live. The model quotes it by id; `checks.py` uses it as an allowlist of legal references.

## Entry format

```json
{
  "id": "cpa_limitation_2y",
  "domain": "refund",
  "title": "Time limit to file a consumer complaint",
  "rule": "A consumer complaint should be filed within two years from when the cause of action arose. The commission can allow a delay only if it records reasons.",
  "plain": "You generally have two years from when the problem happened to file a consumer complaint. A late complaint needs a good reason.",
  "allowed_refs": ["Consumer Protection Act, 2019", "Section 69"],
  "source_url": "TODO: official link (indiacode.nic.in)",
  "verified": false,
  "last_verified": null
}
```
- `domain`: `deposit | refund | both`.
- `rule`: precise statement. `plain`: wording for the user.
- `allowed_refs`: the ONLY statute/section/case names the model may mention when using this entry.
- `verified`: set to `true` **only by a human** after reading the official source. `last_verified`: ISO date.
- `kb.py` validates the file at startup (unique ids, required fields) and refuses to start on errors.

## Loader behaviour (`kb.py`)
- `load_kb()`, `get(id)`, `render_for_prompt(domain)` (compact JSON of `id, title, plain, rule, verified` only), `allowlist()` (normalized set of all `allowed_refs`), `ids()`.
- The chat prompt tells the model to add a "please confirm" note for `verified: false` entries; the UI shows an "unverified" chip beside such `[KB:id]` tags.

## Starter entries (fill `source_url`, verify each, then set `verified: true`)

Entries marked **(sources found)** were consistent across several secondary sources when this plan was written. They still need checking against the Act text. Entries marked **(from memory)** must be treated as unverified.

```json
[
  {
    "id": "cpa_limitation_2y", "domain": "refund",
    "title": "Time limit for a consumer complaint",
    "rule": "A complaint must be filed within two years of the cause of action arising; delay can be condoned if the commission records reasons in writing.",
    "plain": "You generally have two years from when the problem happened to file a consumer complaint. If it is later, you need a good reason for the delay.",
    "allowed_refs": ["Consumer Protection Act, 2019", "Section 69"],
    "source_url": "TODO", "verified": false, "last_verified": null
  },
  {
    "id": "cpa_forum_by_value", "domain": "refund",
    "title": "Which consumer commission by claim value",
    "rule": "District Commission: up to Rs 50 lakh. State Commission: above Rs 50 lakh up to Rs 2 crore. National Commission: above Rs 2 crore. Value is based on the consideration paid (Jurisdiction Rules, 2021).",
    "plain": "For most refund cases (up to Rs 50 lakh paid), you file in the District Consumer Commission.",
    "allowed_refs": ["Consumer Protection Act, 2019", "Section 34", "Section 47", "Section 58", "Consumer Protection (Jurisdiction of the District Commission, the State Commission and the National Commission) Rules, 2021"],
    "source_url": "TODO", "verified": false, "last_verified": null
  },
  {
    "id": "cpa_fee_nil_5lakh", "domain": "refund",
    "title": "Filing fee",
    "rule": "No filing fee for District Commission complaints with claim value up to Rs 5 lakh.",
    "plain": "If your claim is up to Rs 5 lakh, there is no court fee to file.",
    "allowed_refs": ["Consumer Protection Act, 2019"],
    "source_url": "TODO", "verified": false, "last_verified": null
  },
  {
    "id": "cpa_where_to_file", "domain": "refund",
    "title": "Where to file (territorial)",
    "rule": "A complaint can be filed where the opposite party resides or carries on business, where the cause of action arose, or where the complainant resides or personally works for gain.",
    "plain": "You can usually file in the consumer commission of your own city or district.",
    "allowed_refs": ["Consumer Protection Act, 2019", "Section 34"],
    "source_url": "TODO", "verified": false, "last_verified": null
  },
  {
    "id": "cpa_online_filing", "domain": "refund",
    "title": "Online filing",
    "rule": "Consumer complaints can be filed online through the national consumer commission portal (called e-Daakhil; some sources now name e-Jagriti - check the current name).",
    "plain": "You can file the complaint online; check the official consumer commission portal for the current website.",
    "allowed_refs": ["Consumer Protection Act, 2019", "Section 35"],
    "source_url": "TODO", "verified": false, "last_verified": null
  },
  {
    "id": "arb_consumer_no_bar", "domain": "both",
    "title": "Arbitration clause and consumer complaints (from memory)",
    "rule": "The Supreme Court has held (Emaar MGF Land Ltd v. Aftab Singh, 2018) that an arbitration clause in a contract does not stop a consumer from going to a consumer commission.",
    "plain": "Even if your contract has an arbitration clause, you can usually still go to the consumer commission for a consumer dispute. A lawyer should confirm this for your case.",
    "allowed_refs": ["Emaar MGF Land Ltd v. Aftab Singh", "Consumer Protection Act, 2019"],
    "source_url": "TODO", "verified": false, "last_verified": null
  },
  {
    "id": "arb_clause_basics", "domain": "both",
    "title": "What an arbitration clause is (from memory)",
    "rule": "An arbitration clause sends disputes to a private arbitrator instead of a court. Under the Arbitration and Conciliation Act, 1996 the agreement must be in writing (Section 7). A person connected to one side may be ineligible to act as arbitrator (Section 12(5) and the Seventh Schedule).",
    "plain": "An arbitration clause means disputes may be decided by a private arbitrator, not a court. If the other party alone picks the arbitrator, ask a lawyer whether that is allowed.",
    "allowed_refs": ["Arbitration and Conciliation Act, 1996", "Section 7", "Section 12(5)", "Seventh Schedule"],
    "source_url": "TODO", "verified": false, "last_verified": null
  },
  {
    "id": "arb_notice_urgent", "domain": "both",
    "title": "Arbitration notice or award is urgent (from memory)",
    "rule": "Deadlines to respond to an arbitration notice or to challenge an award in court are short (a challenge is generally within about three months, with limited extension). Always see a lawyer immediately.",
    "plain": "If you received an arbitration notice or an award, time limits are short. Please speak to a lawyer or your DLSA right away.",
    "allowed_refs": ["Arbitration and Conciliation Act, 1996", "Section 34"],
    "source_url": "TODO", "verified": false, "last_verified": null
  },
  {
    "id": "ecom_grievance_officer", "domain": "refund",
    "title": "E-commerce grievance officer (from memory)",
    "rule": "Under the Consumer Protection (E-Commerce) Rules, 2020, e-commerce entities must have a grievance officer who acknowledges a complaint within 48 hours and resolves it within one month.",
    "plain": "For online shopping, first complain to the platform's grievance officer in writing and keep the acknowledgement.",
    "allowed_refs": ["Consumer Protection (E-Commerce) Rules, 2020"],
    "source_url": "TODO", "verified": false, "last_verified": null
  },
  {
    "id": "consumer_helpline", "domain": "refund",
    "title": "National Consumer Helpline (from memory)",
    "rule": "The National Consumer Helpline (toll-free 1915) accepts consumer grievances and tries to resolve them with the company before litigation.",
    "plain": "You can also call the National Consumer Helpline (1915) to try to settle the matter before filing a case.",
    "allowed_refs": [],
    "source_url": "TODO", "verified": false, "last_verified": null
  },
  {
    "id": "deposit_no_central_law", "domain": "deposit",
    "title": "Deposit rules depend on the state (from memory)",
    "rule": "There is no single central law fixing security-deposit rules for all tenancies. States have their own rent laws. The Model Tenancy Act, 2021 is a template that applies only where a state has adopted it. The signed agreement matters most.",
    "plain": "Deposit rules depend on your state and on your agreement. Tell me your state and let's check your agreement.",
    "allowed_refs": ["Model Tenancy Act, 2021"],
    "source_url": "TODO", "verified": false, "last_verified": null
  },
  {
    "id": "deposit_forum_civil", "domain": "deposit",
    "title": "Where deposit disputes go (from memory)",
    "rule": "A landlord-tenant deposit dispute is generally a civil money-recovery matter (civil court, or the rent authority/court where the state law provides one), not a consumer commission matter.",
    "plain": "A deposit dispute with a landlord usually goes to a civil court or your state's rent authority, not the consumer commission. A lawyer can tell you which applies in your state.",
    "allowed_refs": [],
    "source_url": "TODO", "verified": false, "last_verified": null
  },
  {
    "id": "deposit_limitation_3y", "domain": "deposit",
    "title": "Time limit for recovering money (from memory)",
    "rule": "A civil suit to recover money is generally subject to a three-year limitation period under the Limitation Act, 1963, counted from when the right to sue arose. The exact starting point depends on the facts.",
    "plain": "Money-recovery cases usually have about a three-year time limit, so do not wait too long. A lawyer can confirm the exact date for you.",
    "allowed_refs": ["Limitation Act, 1963"],
    "source_url": "TODO", "verified": false, "last_verified": null
  },
  {
    "id": "legal_notice_optional", "domain": "both",
    "title": "Legal notice before action (from memory)",
    "rule": "Sending a written legal notice before filing a case is common practice and shows you asked first. It is generally not required for private disputes, though special rules apply to claims against government bodies.",
    "plain": "A written notice asking for your money back is a good first step. Send it by a method that gives proof, like registered post, and keep a copy.",
    "allowed_refs": [],
    "source_url": "TODO", "verified": false, "last_verified": null
  },
  {
    "id": "free_legal_aid", "domain": "both",
    "title": "Free legal aid (from memory)",
    "rule": "District Legal Services Authorities (DLSA) under the Legal Services Authorities Act, 1987 provide free legal aid to eligible persons.",
    "plain": "If cost is a worry, your District Legal Services Authority (DLSA) may give you a lawyer for free if you qualify.",
    "allowed_refs": ["Legal Services Authorities Act, 1987"],
    "source_url": "TODO", "verified": false, "last_verified": null
  }
]
```

## Maintenance rules
- Add an entry only with an official source link. Prefer the Act text on indiacode.nic.in and official consumer-affairs pages.
- Re-verify entries every quarter; update `last_verified`.
- A lawyer reviews the file before any real-world use. State this in the submission doc.
- To cover a new state or topic, add entries with a `state` field (future work) and extend tests.
