# Native compiler authority

- The most recently executed component build/test result owns current blocker state.
- Resolve compiler paths relative to the command's component working directory before choosing a repair target.
- A green component is frozen while a different component has a fresh native compiler failure.
- Definition/trait/schema diagnostics may target the canonical provider; ordinary type/call mismatches target the primary compiler location.
- Try distinct compiler-owned targets only once per accepted repository revision, then stop with exact evidence instead of rotating into unrelated files.
- A native repair is progress only when replay of the same component strictly reduces its compiler error count or passes.
- These rules apply to Rust/Cargo, Go, .NET, JVM, C/C++, Swift, Dart/Flutter, and custom declared toolchains.
