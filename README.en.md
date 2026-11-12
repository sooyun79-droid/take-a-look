# Take a Look · v0.3.0-alpha

**ALPHA SOFTWARE**. AI found a bug? Take a Look tries to prove it first.

A read-only local auditor for people who built software with AI. It separates hypotheses, independent challenges, deterministic evidence and verdicts. LLM confidence alone never confirms a bug.

## Quick start

### 1) One-line run (recommended)

No clone and no `git pull`. The `npx` form needs Node 20+ and finds Python itself; Python 3.11+ is required either way, because the auditor is a Python program (npm does not install Python).

```text
# with Python 3.11+ (pipx)
pipx run --spec git+https://github.com/sooyun79-droid/take-a-look.git take-a-look audit <folder>

# with Node 20+ (npx)
npx github:sooyun79-droid/take-a-look audit <folder>
```

To keep it installed: `pipx install git+https://github.com/sooyun79-droid/take-a-look.git`, then run `take-a-look audit <folder>`. Reports are written to `reports/<id>/report.html` under the folder you ran it in. After a completed audit, exit code 1 means confirmed findings; exit code 2 means an invalid target or incomplete inspection, including a missing/failed Node/TypeScript analyzer. A missing or older Python stops with exit code 1 after a setup hint. Installed packages include the pinned TypeScript parser; Node itself remains a prerequisite for Node/TypeScript analysis.

### 2) Download (non-developers, Windows)

Download `take-a-look-v0.3.0-alpha.zip` from the [release](https://github.com/sooyun79-droid/take-a-look/releases/tag/v0.3.0-alpha) and unzip it. On Windows double-click `Start-TakeALook.cmd`; on macOS/Linux run this inside the unzipped folder:

```text
python3 -B take-a-look.pyz web --open
```

The ZIP carries the Python zipapp and the TypeScript parser, so no clone or `npm ci` is needed; Python 3.11+ is still required. Running from a source checkout instead:

```text
npm ci --ignore-scripts --no-audit --no-fund
python -B -m take_a_look web --open
```

The UI is Korean. Enter a local project path. Offline rule discovery is the default; OpenAI is optional and real API evaluation remains NOT_RUN in this environment. Limited Python and Node/TypeScript AST checks never import target code. Docker integration remains unvalidated here; there is no safety guarantee.

Verdicts: CONFIRMED, REFUTED, UNCONFIRMED, NEEDS_HUMAN. Web/e-commerce static patterns remain UNCONFIRMED until a real defect is proven; payment amount literals do not prove missing server-side checks. Discovery attribution: RULE, LLM, BOTH. Source hashes, evidence IDs, execution mode, call counts and available token usage are preserved. Unknown costs and unmeasured false-positive rates are null. The GitHub Action defaults to report-only (`fail-on-confirmed: false`); incomplete inspection always exits 2.

### 3) GitHub Action (CI/CD)

Audit every pull request and report into the PR comment and Step Summary. Paste the three workflow lines from the next section; inputs, exit codes and fork limits are in [docs/github-action.md](docs/github-action.md).

## GitHub Action for pull requests

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

See [Korean guide](README.md), [sample](docs/sample-report.md), [security](SECURITY.md), [evaluation](docs/benchmark-003.md), [contributing](CONTRIBUTING.md) and [MIT license](LICENSE). The bundled TypeScript parser remains Apache-2.0.
