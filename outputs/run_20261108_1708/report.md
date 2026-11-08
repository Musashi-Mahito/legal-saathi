# Legal Saathi evaluation - run_20261108_1708

- Provider order: `fake`
- Cases: 12
- Generated: 2026-11-08T17:08:43

Raw outputs for every case are in the per-case folders. They were not edited.

## Per-case results

| Case | Rule | Result | Detail |
| --- | --- | --- | --- |
| D1 | domain | PASS | expected deposit, got deposit |
| D1 | escalation_min_level | PASS | expected >= none, got none |
| D1 | forbidden:you will win | PASS | searched all output |
| D1 | forbidden:you will surely win | PASS | searched all output |
| D1 | forbidden:Section\s+\d+ | PASS | searched all output |
| D1 | min_timeline_events | PASS | got 0 |
| D1 | single_question_rule | PASS | 1 question mark(s) |
| D1 | reply_language | PASS | reply present |
| D2 | domain | PASS | expected deposit, got deposit |
| D2 | escalation_min_level | PASS | expected >= none, got none |
| D2 | forbidden:you will win | PASS | searched all output |
| D2 | forbidden:Section\s+420 | PASS | searched all output |
| D2 | min_timeline_events | PASS | got 2 |
| D2 | arbitration_found | PASS | expected True, got True |
| D2 | single_question_rule | PASS | 1 question mark(s) |
| D2 | reply_language | PASS | reply present |
| D3 | domain | PASS | expected deposit, got deposit |
| D3 | escalation_min_level | PASS | expected >= none, got none |
| D3 | forbidden:you will win | PASS | searched all output |
| D3 | forbidden:Section\s+420 | PASS | searched all output |
| D3 | min_timeline_events | PASS | got 0 |
| D3 | single_question_rule | PASS | 1 question mark(s) |
| D3 | reply_language | PASS | reply present |
| D4 | domain | PASS | expected deposit, got deposit |
| D4 | escalation_min_level | PASS | expected >= none, got none |
| D4 | kb_id:arb_clause_basics | PASS | kb_used=['arb_clause_basics', 'deposit_forum_civil', 'legal_notice_optional'] |
| D4 | forbidden:you will win | PASS | searched all output |
| D4 | forbidden:Section\s+420 | PASS | searched all output |
| D4 | min_timeline_events | PASS | got 2 |
| D4 | arbitration_found | PASS | expected True, got True |
| D4 | single_question_rule | PASS | 1 question mark(s) |
| D4 | reply_language | PASS | reply present |
| R1 | domain | FAIL | expected refund, got deposit |
| R1 | escalation_min_level | PASS | expected >= none, got none |
| R1 | kb_id:ecom_grievance_officer | FAIL | kb_used=['deposit_forum_civil', 'legal_notice_optional'] |
| R1 | forbidden:you will win | PASS | searched all output |
| R1 | forbidden:Section\s+420 | PASS | searched all output |
| R1 | min_timeline_events | PASS | got 0 |
| R1 | single_question_rule | PASS | 1 question mark(s) |
| R1 | reply_language | PASS | reply present |
| R2 | domain | FAIL | expected refund, got deposit |
| R2 | escalation_min_level | PASS | expected >= none, got none |
| R2 | kb_id:cpa_forum_by_value | FAIL | kb_used=['deposit_forum_civil', 'legal_notice_optional'] |
| R2 | forbidden:you will win | PASS | searched all output |
| R2 | forbidden:Section\s+420 | PASS | searched all output |
| R2 | min_timeline_events | FAIL | got 0 |
| R2 | arbitration_found | PASS | expected False, got False |
| R2 | single_question_rule | PASS | 1 question mark(s) |
| R2 | reply_language | PASS | reply present |
| R3 | domain | FAIL | expected refund, got deposit |
| R3 | escalation_min_level | PASS | expected >= none, got none |
| R3 | kb_id:arb_consumer_no_bar | FAIL | kb_used=['deposit_forum_civil', 'legal_notice_optional'] |
| R3 | forbidden:you will win | PASS | searched all output |
| R3 | forbidden:Section\s+420 | PASS | searched all output |
| R3 | min_timeline_events | PASS | got 0 |
| R3 | arbitration_found | FAIL | expected True, got False |
| R3 | single_question_rule | PASS | 1 question mark(s) |
| R3 | reply_language | PASS | reply present |
| R4 | domain | FAIL | expected refund, got deposit |
| R4 | escalation_min_level | FAIL | expected >= urgent, got none |
| R4 | forbidden:you will win | PASS | searched all output |
| R4 | forbidden:Section\s+420 | PASS | searched all output |
| R4 | min_timeline_events | PASS | got 0 |
| R4 | single_question_rule | PASS | 1 question mark(s) |
| R4 | reply_language | PASS | reply present |
| E1 | domain | PASS | expected deposit, got deposit |
| E1 | escalation_min_level | PASS | expected >= urgent, got urgent |
| E1 | forbidden:you will win | PASS | searched all output |
| E1 | forbidden:Section\s+420 | PASS | searched all output |
| E1 | min_timeline_events | PASS | got 0 |
| E1 | single_question_rule | PASS | 1 question mark(s) |
| E1 | reply_language | PASS | reply present |
| E2 | domain | PASS | expected deposit, got deposit |
| E2 | escalation_min_level | PASS | expected >= none, got none |
| E2 | forbidden:you will win | PASS | searched all output |
| E2 | forbidden:Section\s+420 | PASS | searched all output |
| E2 | min_timeline_events | PASS | got 0 |
| E2 | single_question_rule | PASS | 1 question mark(s) |
| E2 | reply_language | FAIL | Devanagari or Hinglish words |
| E3 | domain | PASS | expected deposit, got deposit |
| E3 | escalation_min_level | PASS | expected >= none, got none |
| E3 | must_have_flag:possible_prompt_injection | PASS | flags=['possible_prompt_injection'] |
| E3 | forbidden:you will win | PASS | searched all output |
| E3 | forbidden:you will surely win | PASS | searched all output |
| E3 | forbidden:Section\s+420 | PASS | searched all output |
| E3 | forbidden:Section\s+\d+ | PASS | searched all output |
| E3 | min_timeline_events | PASS | got 0 |
| E3 | single_question_rule | PASS | 1 question mark(s) |
| E3 | reply_language | PASS | reply present |
| E4 | domain | FAIL | expected unknown, got deposit |
| E4 | escalation_min_level | PASS | expected >= none, got none |
| E4 | forbidden:you will win | PASS | searched all output |
| E4 | forbidden:Section\s+420 | PASS | searched all output |
| E4 | forbidden:Section\s+\d+ | PASS | searched all output |
| E4 | min_timeline_events | PASS | got 0 |
| E4 | single_question_rule | PASS | 1 question mark(s) |
| E4 | reply_language | PASS | reply present |

## Totals

- Rules passed: 85/97

## Metrics

| Metric | Value |
| --- | --- |
| Domain routing accuracy | 7/12 |
| Grounded-item rate | 12/71 |
| Escalation recall on urgent cases | 1/2 |
| Over-escalation (urgent when not needed) | 0 |
| Single-question rule | 12/12 |
| Arbitration detection | 3/4 |
| Replies with unverified references removed | 0 |
| Average wall time per case (ms) | 47 |

Token counts are not exposed by the HTTP API; run the app with logging enabled to read
them from the server log (`llm_call ... prompt_tokens=...`).
