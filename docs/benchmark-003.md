# Alpha evaluation — private project aggregate only

Date: 2026-09-19. Source, personal paths, project metadata and raw private reports are deliberately excluded from this public document.

**SEARCHLENS_003_REAL_LLM=NOT_RUN**. No API key/model was configured. The #003 measurements below are a separately labeled **offline rule recheck**, not a mock disguised as live LLM evaluation.

| Metric | #001 | #002 | #003 offline recheck |
|---|---:|---:|---:|
| Initial claims | 21 | 21 | 21 |
| Rule claims | 21 | 21 | 21 |
| LLM claims / overlap | 0 / 0 | 0 / 0 | 0 / 0 |
| CONFIRMED | 0 | 0 | 0 |
| REFUTED | 0 | 6 | 6 |
| UNCONFIRMED | 21 | 15 | 15 |
| NEEDS_HUMAN | 0 | 0 | 0 |
| Display groups | 21 individual | 1 | 1 |
| Node execution evidence claims | 0 | 7 | 7 |
| LLM calls | 0 | 0 | 0 |
| Execution mode | limited analysis | limited analysis | SAFE_LOCAL_LIMITED |

The seven claims with execution evidence include one partially checked claim that remains UNCONFIRMED. Five claims have guard evaluations and two have limited function-body reproductions. These are not full application executions.

Duration: 6.852 seconds for #003 pipeline. Tokens and estimated API cost: unavailable/null. No API charge was incurred by this run. Included-source hashes, Git status and mapped metadata were unchanged before/after; 357 included files were compared. Excluded secrets/dependencies are outside the content-hash scope.

## Questions this evaluation can and cannot answer

1. Did a real LLM find rule-missed issues? **Not evaluated: no real calls.**
2. Were any LLM-only issues objectively confirmed? **Not evaluated.**
3. How many real LLM claims were refuted? **No real LLM claims were generated; capability not measured.**
4. Did an LLM increase false-positive candidates? **Not evaluated.** A refuted initial hypothesis is not a confirmed false-positive verdict.
5. Were the previous 15 unresolved claims resolved? **No. All 15 remain unresolved.**
6. Did the suite pass and then a new real issue appear? **Not established. The private project's suite was not run.** The authored fixture C does demonstrate this narrower scenario.
7. Was LLM use worth the cost? **Not evaluated.** No price assumptions are fabricated.

## Auditor tests

Python 59 tests and Node 11 tests passed locally. TypeScript fixture typecheck and syntax/config checks passed. A–H remain covered. I/J use a **scripted provider replay** to simulate rule-missed claims and a separately authored user oracle: I is CONFIRMED, J REFUTED. Without that oracle they remain UNCONFIRMED. This proves pipeline behavior, not model intelligence. K–O cover injection, dangerous commands, redaction and grouping. Existing policy fixtures exercise NEEDS_HUMAN.

Docker integration and live OpenAI requests were not run. Dedicated lint and wheel builds were not run; syntax checks and zipapp/ZIP builds are distinct. GitHub CI results, if any, must be read from GitHub rather than inferred from this local test record.
