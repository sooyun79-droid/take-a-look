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

### GitHub Action

Verify AI-written pull requests in CI and post the result as a PR comment:

```yaml
name: Take a Look Audit
on: [pull_request]
permissions:
  contents: read
  pull-requests: write
jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: sooyun79-droid/take-a-look@main
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

No API key or pip package is needed; reports are written outside the checked-out folder and the same PR comment is updated on every run. Setup, inputs, exit codes and fork limitations are in [docs/github-action.md](docs/github-action.md) (Korean).

See [Korean guide](README.md), [sample](docs/sample-report.md), [security](SECURITY.md), [evaluation](docs/benchmark-003.md), [contributing](CONTRIBUTING.md) and [MIT license](LICENSE). The separately installed TypeScript parser remains Apache-2.0.
