# 떼껄룩 Take a Look — Release notes

## v0.3.1-alpha

Pre-release. Fixes verdict strictness and packaging after v0.3.0-alpha; v0.3.0-alpha stays published unchanged.

- Web/e-commerce static rules keep pattern presence at UNCONFIRMED: finding `seo_noindex`, `client_secret_leak`, `a11y_image_alt` or `client_payment_tamper` patterns never confirms a defect by itself.
- Payment-tamper discovery no longer mistakes quoted strings and comments for real payment calls, removing a class of false positives.
- TypeScript 5.9.3 analyzer ships inside the package and the ZIP (`take_a_look/vendor/typescript.js`); no tool is resolved or installed from the audited repository.
- A missing or failed Node/TypeScript analyzer is reported as INCOMPLETE (inspection not completed) with exit code 2 instead of being treated as a pass.
- GitHub Action `fail-on-confirmed` now defaults to `false` (report-only); incomplete inspection still exits 2 regardless of that input.
- One-line run without cloning: `npx github:sooyun79-droid/take-a-look` (Node 20+) or `pipx run --spec git+https://github.com/sooyun79-droid/take-a-look.git` (Python 3.11+).
- Offline GUI dashboard bundle `take-a-look-v0.3.1-alpha.zip` (Python zipapp, `Start-TakeALook.cmd`, bundled TypeScript parser).

Limitations: no real API evaluation in this environment; Docker integration not validated; bounded checks are not app-wide execution or security assurance. No auto-fix, telemetry, deployment or private-repository authentication.

## v0.3.0-alpha

Release candidate: v0.3.0-alpha. First public alpha preparation.

- Distinguish AI claims from verified facts.
- Independent Investigator / Challenger contexts.
- Rule / LLM / overlap attribution through final verdicts.
- Deterministic Python and limited Node/TypeScript verification.
- Explicit user-contract checks; no model-invented oracle.
- Offline mock and opt-in OpenAI adapter.
- Korean local UI, grouped findings and readable evidence.
- Prompt-injection, command-policy and secret-redaction fixtures.
- Composite GitHub Action (`.github/workflows` sample in `docs/github-action.md`): audits pull requests, writes the Step Summary and upserts one PR comment; no API key or pip package, reports kept outside the checkout.

Limitations: no real API evaluation in this environment; Docker integration not validated; bounded checks are not app-wide execution or security assurance. No auto-fix, telemetry, deployment or private-repository authentication.
