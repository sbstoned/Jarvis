JARVIS V36.1.0 - REAL-RUN HARDENING
====================================

V36.1 is the recommended replacement for V36.0.

The release specifically hardens failures observed during the first TaskForge V36 run:

1. Multiple explicit stacks are locked independently. A prompt that explicitly requests
   React/TypeScript/Vite for the frontend and Python/FastAPI for the backend remains a
   two-component project. Planner metadata cannot silently replace it with Expo.

2. Runtime names are no longer assumed to be filenames. "Node.js installed" does not
   create a source file named Node.js unless the user explicitly asks for that file.

3. Single-file transport salvage recognizes malformed END FILE markers and discards
   accidental source continuation after the transport boundary.

4. Requirements compilation keeps a deterministic source-requirement ledger and coverage
   mapping so explicit bullets and acceptance criteria cannot quietly disappear.

5. Shared contracts are canonicalized before implementation to reduce repeated/conflicting
   schema definitions.

6. Embedded SQLite DDL is actually parsed by SQLite before a Python database candidate can
   be accepted.

7. Python async-generator/context-manager misuse is detected before later code is built on
   an invalid provider contract.

8. Windows delivery commands are guarded against common POSIX-only planner output.

9. Foundation/contract defects discovered immediately after a file is generated trigger a
   targeted repair rather than waiting for the end-of-project acceptance phase.

All V36 repository-map, machine-contract, patch-first repair, checkpoint, dynamic-context,
role separation, stack skills, multi-component validation, and clean-environment features
remain enabled.

Run CHECK_V361_ALL.bat after installation to run all 82 deterministic regression checks.
