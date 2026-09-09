Jarvis V42.29 - Last-Mile Constraint Solver + Acceptance Closure

Purpose
-------
V42.29 keeps the V42.26 repair pipeline that proved capable of reducing large
TypeScript error sets, plus V42.27 parser safety and V42.28 best-state promotion.
It specifically closes the small compiler tail that could still cause Jarvis to
save a checkpoint instead of reaching final acceptance.

Key changes
-----------
1. Small TypeScript tails up to 12 diagnostics enter a deterministic constraint
   solver before more broad model reasoning.
2. Missing React props are wired from EXISTING hook/service producers. Jarvis
   never weakens the child Props interface or invents placeholder values.
3. Hook/service member mismatches inspect the provider's actual returned object
   keys and alias the consumer binding when the relationship is exact.
4. Typed CSV line parsers may be reconstructed from a local row interface plus
   an explicit CSV header when compiler evidence proves Partial<T> is being used
   where complete T is required.
5. boolean -> "true"/"false" roundtrips are removed when the declared record
   field is boolean.
6. Every deterministic multi-file candidate is provisional until a fresh whole
   TypeScript compile strictly reduces diagnostics. No ts-ignore, compiler-option
   weakening, Props weakening, or unsafe placeholder values are used.
7. Acceptance may continue boundedly while fresh compiler quality is strictly
   improving instead of checkpointing immediately after a proven small-tail gain.
8. V42.28 best-state scoring remains authoritative, so a worse later trial can
   never replace the lowest-error verified working state.

GearTrack regression represented by this release
-------------------------------------------------
The retained 8-error checkpoint had three root-cause groups:
- App.tsx: 3 required component props not wired.
- useTools.ts: 2 consumer aliases did not match the existing hook API.
- useCSVImportExport.ts: 3 typed CSV record/parser errors.

V42.29's deterministic solver resolves all three groups in a staged candidate.
The user's real npm/Tauri toolchain remains the final integration authority.
