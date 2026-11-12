# Architecture and evidence boundaries

Mapper -> independent Rule / LLM discovery -> provenance merge -> Challenger -> closed VerificationIntent -> deterministic QA -> EvidenceJudge -> Korean report.

Provider.complete(RoleRequest) is the adapter interface. Investigator and Challenger receive separate requests, purposes and contexts. The challenger does not receive investigator confidence or reasoning. OpenAI Responses uses strict structured JSON without tools. Responses are validated locally and repository content is marked untrusted.

Claims store RULE / LLM / BOTH. Overlap requires the same rule, file and line; uncertain semantic matches remain separate. Fallback output is RULE. Grouping summarizes a verification pattern, not proof that every location has one root cause.

Verification intents are CHECK_SYNTAX, CHECK_BOUNDARY, CHECK_CONTRACT, CHECK_STATIC_PATTERN, HUMAN_REVIEW, NO_EXECUTION. Fixed runners use argv with shell=False. No LLM-generated command strings execute. An unrecognized intent or path traversal is rejected.

CHECK_STATIC_PATTERN re-reads the same file with the closed web/e-commerce rule set (seo_noindex, client_secret_leak, a11y_image_alt, client_payment_tamper) and reports whether the pattern is still at the claimed line. Pattern presence alone yields UNCONFIRMED, never a confirmed defect; deployment intent, server-side validation and app-wide impact stay with the human. Payment discovery excludes quoted strings and comments as calls. Detection for the investigator role reads the redacted snapshot, so only names and masked placeholders survive into a claim, never secret values.

For a contract claim, an explicit user contract is required. Pass --contracts with a JSON file outside the audited folder. Example content:

```json
{"calc.py::discounted":{"inputs":{"price":200,"percent":10},"expected":180}}
```

This only verifies that specific input and expectation under the bounded Python function interpreter. The oracle is supplied by the user, never inferred as truth from repository text or LLM output. Without it the claim remains UNCONFIRMED. CLI exposes contracts; the minimal web UI does not yet configure them.

SAFE_LOCAL_LIMITED means bounded interpreter evidence, not full app execution. DOCKER_SANDBOX requires container-ID evidence; NO_EXECUTION means no execution evidence. Container suite status never promotes individual claims.

Installed Python/npm packages and the GitHub Action carry the pinned TypeScript parser. The ZIP retains its parser sidecar. If Node or the parser is unavailable, or the worker fails, a Node/TypeScript project is marked INCOMPLETE; the CLI and Action exit 2. This is distinct from both an unproven claim and a confirmed defect.

Audit logs link claims, challenges, plans, evidence and verdicts. Regression candidates retain inputs/observations for later manual adoption. Source files are not rewritten. Metrics split discovery origins and outcomes, track calls/tokens/duration, and keep unmeasured API costs and false-positive rates null.
