# Take a Look · v0.3.0-alpha

**ALPHA SOFTWARE**. AI found a bug? Take a Look tries to prove it first.

A read-only local auditor for people who built software with AI. It separates hypotheses, independent challenges, deterministic evidence and verdicts. LLM confidence alone never confirms a bug.

Python 3.11+ and Node 20+ are prerequisites. From this project's folder:

```text
npm ci --ignore-scripts --no-audit --no-fund
python -B -m take_a_look web --open
```

The UI is Korean. Enter a local project path. Offline rule discovery is the default; OpenAI is optional and real API evaluation remains NOT_RUN in this environment. Limited Python and Node/TypeScript AST checks never import target code. Docker integration remains unvalidated here; there is no safety guarantee.

Verdicts: CONFIRMED, REFUTED, UNCONFIRMED, NEEDS_HUMAN. Discovery attribution: RULE, LLM, BOTH. Source hashes, evidence IDs, execution mode, call counts and available token usage are preserved. Unknown costs and unmeasured false-positive rates are null.

See [Korean guide](README.md), [sample](docs/sample-report.md), [security](SECURITY.md), [evaluation](docs/benchmark-003.md), [contributing](CONTRIBUTING.md) and [MIT license](LICENSE). The separately installed TypeScript parser remains Apache-2.0.
