# Transactional compile gate

- Never write model output directly into authoritative source and call it progress.
- Stage the candidate, parse it with the language's available parser/compiler, then run relevant contract/import checks.
- For a repair driven by a real compiler/build/test failure, replay that validator in a disposable project when the failure names the target.
- Commit only if syntax is valid and the proven failure disappears or advances; otherwise restore the accepted revision.
- Terminal commands, prose, Markdown fences, and tool output are not source code.
- This rule applies to every language/toolchain, including custom components through their declared verification commands.
