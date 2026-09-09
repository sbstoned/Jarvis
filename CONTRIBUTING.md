# Contributing to Jarvis

Thanks for your interest in contributing to Jarvis.

Jarvis is intended to remain a general-purpose AI software builder rather than becoming tightly coupled to one language, framework, engine, or toolchain.

## Core contribution principles

- Prefer compiler, test, runtime, and toolchain evidence over model confidence.
- Preserve the best verified project state when attempting repairs.
- Do not weaken acceptance gates just to make a project appear complete.
- Keep model routing separate from the underlying project-building architecture.
- Avoid hard-coded machine paths, credentials, usernames, or private configuration.
- Keep stack-specific behavior isolated behind adapters or skills whenever possible.

## Useful contribution areas

- model routing and health checks
- toolchain detection
- sandbox and command safety
- planning and project-state management
- build and repair loops
- acceptance and regression testing
- checkpoint and resume behavior
- dashboard and voice features
- cross-platform support
- language, framework, engine, and build-system skills

## Pull requests

A pull request should explain:

1. The problem being solved.
2. The likely root cause.
3. The files or subsystems changed.
4. How the change was tested.
5. Whether acceptance, repair, routing, or safety behavior changed.

Changes should preserve existing build, test, runtime, checkpoint, validation, and toolchain behavior unless the pull request intentionally changes that behavior and explains why.

## Security

Never commit API keys, passwords, access tokens, certificates, private environment files, user uploads, or other sensitive data.

For security-sensitive issues, follow the guidance in `SECURITY.md` instead of posting credentials or exploit details publicly.

## License

By contributing to Jarvis, you agree that your contributions may be distributed under the project MIT License.
