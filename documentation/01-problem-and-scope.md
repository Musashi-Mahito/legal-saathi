# 1. Problem and scope

## The problem

Most people in India cannot afford a lawyer for a small dispute, and the amounts
are too small to justify one. Two situations repeat constantly:

1. **The tenant security deposit.** A tenant vacates, the landlord goes silent or
   deducts far more than the agreement allows, and the tenant has no idea where a
   deposit dispute even belongs (civil court? rent authority? consumer
   commission?).
2. **The consumer refund.** A product is returned, a service is never delivered,
   and the refund simply does not arrive. The person does not know that an
   e-commerce grievance officer exists, that the helpline is 1915, or that there
   is a two-year window.

In both cases the person's real question is not "what is the law" but *"what do I
do next, and how long do I have?"*

## Why these two, and not others

| Criterion | Deposit | Refund |
|---|---|---|
| Happens to almost everyone | Yes, every tenancy ends | Yes, online shopping is routine |
| Amount too small for a lawyer | Typically ₹20,000–₹2,00,000 | Typically ₹2,000–₹50,000 |
| A known forum exists | Civil court / state rent authority | District Consumer Commission |
| Documents usually exist | Rent agreement, receipts | Invoice, warranty, chats |

Because both have a **known forum and a known time limit**, the assistant can give
genuinely useful direction without guessing. That is not true of, say, a family
dispute, where the right advice depends on facts an app cannot see.

## The arbitration-clause problem

Both domains bury one clause that misleads people: *"any dispute shall be referred
to a sole arbitrator appointed by the Company/Landlord."* A person reading that
concludes they have signed away the right to complain. They usually have not for a
consumer dispute. So the app explicitly detects the clause, quotes it, explains it
in plain words, and — because the underlying knowledge entry is unverified —
tells the user to confirm with a lawyer.

## In scope

- Tenant security-deposit disputes: non-return, unfair deduction, delayed refund.
- Consumer refund / defective goods / service-not-delivered disputes.
- Arbitration-clause detection and plain explanation.
- Replies in English, Hindi or Hinglish.
- Documents: text-based PDF, DOCX, TXT (rental agreement, invoice, warranty,
  terms and conditions, notice).
- A draft legal notice with placeholders for missing facts.

## Deliberately out of scope

| Excluded | Why |
|---|---|
| Criminal matters | Wrong forum, and the cost of a wrong answer is unacceptable |
| Eviction defence | Urgent, fact-specific, and the user needs a lawyer *now* |
| Cheque bounce | Strict statutory timelines; a chatbot is the wrong tool |
| Family, property, tax law | Highly fact-dependent, no single correct next step |
| OCR / scanned PDFs / photos | Not supported; the upload is rejected with a clear message |
| Voice input | Not built |
| Court filing | Not built |
| User accounts, database | Everything is a single in-memory session |

An out-of-scope message is not answered with a guess. The assistant sets
`domain: "out_of_scope"`, says so kindly, and points to a lawyer or the District
Legal Services Authority (DLSA).

## Who this is for

An urban smartphone user with an English, Hindi or Hinglish comfort level, who has
some documents and no lawyer. The interface is a single mobile-friendly page with
no login, because asking someone to create an account before they know whether
the tool helps is a bad trade.

## What "done" means here

The app is useful if a person finishes a session knowing:

1. whether their problem is a deposit or a refund problem,
2. which forum it belongs in, and why,
3. the deadline that applies to them,
4. the two or three things to do this week, and
5. whether they need a lawyer urgently.

Everything else — the timeline, the summary, the draft notice — exists to support
those five answers.
