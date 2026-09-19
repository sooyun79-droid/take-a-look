# Security model and alpha limitations

This is experimental evidence-oriented auditing, not a complete security scanner or safety guarantee. Treat target files as hostile data. Do not publish secrets or private source in issues.

Local mode never imports/evals target modules. Closed AST interpreters reject unsupported operations, but parsers/interpreters are not an OS security boundary. Resource limits and snapshot hashes do not eliminate concurrent filesystem attacks or parser vulnerabilities. Use an isolated machine for hostile repositories.

Docker runner integration has NOT been validated in the current development environment. It accepts a preinstalled trusted sha256 image, never pulls, runs non-root with no network/capabilities, mounts only a selected readonly snapshot, and uses bounded writable tmpfs plus process/resource/time limits. Docker client access remains on the host; its socket is never mounted into the container. Container cleanup cannot be guaranteed if the daemon disconnects. Images may contain their own configuration; only use images you have independently vetted.

Repository stdout/stderr can contain secrets and forged test summaries; the suite stores structural results only and cannot establish a Claim verdict. LLM proposals cannot supply shell commands or their own authoritative test oracle. Explicit user contracts come from outside the target folder.

.env, key files, dependencies and links are excluded; pattern redaction is not complete DLP. OpenAI is opt-in and sends filtered/redacted code externally. No telemetry. API keys are process environment only, never logged. Unknown provider failures fail closed or visibly fall back to rules.

If GitHub private vulnerability reporting is available, use it for sensitive disclosures. Otherwise report only a non-sensitive summary asking maintainers for a private channel; do not attach exploit secrets publicly.
