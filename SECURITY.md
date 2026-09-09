# Security Policy

Security issues are taken seriously in Jarvis, especially because the project can execute development commands, modify project files, interact with local models, and optionally connect to external AI providers.

## Reporting a vulnerability

Please do not publish credentials, API keys, private data, exploit details, or other sensitive information in a public GitHub issue.

Security-sensitive reports may include:

- credential or API-key exposure
- commands escaping the selected project workspace
- unintended arbitrary command execution
- unsafe file deletion or overwrite behavior
- sandbox or validation bypasses
- leakage of private prompts, sessions, uploads, or runtime data
- provider credentials being written to logs or generated projects

If GitHub Private Vulnerability Reporting is enabled for this repository, use that mechanism. Otherwise, contact the maintainer privately through the GitHub profile rather than posting sensitive details publicly.

## Secrets and credentials

Never commit:

- API keys
- passwords or access tokens
- private `.env` files
- certificates or private keys
- user uploads
- private runtime sessions or memory

Local provider configuration such as `ai_providers.env` is intentionally excluded from the public repository.

## Local execution risk

Jarvis can execute local development tools and commands. Generated, downloaded, or model-produced code should be treated as untrusted until reviewed and validated.

Use Jarvis only in environments where you understand and accept the risks of executing third-party or AI-generated code.

## Supported versions

Jarvis is under active development. Security fixes currently target the latest version of the `main` branch.
