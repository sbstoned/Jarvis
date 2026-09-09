JARVIS V33 SYSTEMATIC PROJECT BUILD
==================================

WHY V33 EXISTS
--------------
V32 could successfully hold a 262,144-token Qwen3.5 context, but project bootstrap still generated
one complete file at a time before the rest of the repository had concrete interfaces. This made
large early files slow and encouraged cross-file API guessing.

V33 changes repository construction to:

  USER REQUEST
      -> architecture reasoning
      -> strict project contract manifest
      -> dependency graph + exact public signatures
      -> visible contract skeleton repository
      -> foundation/models/config
      -> data/persistence
      -> services/domain logic
      -> UI
      -> thin entrypoint/integration
      -> tests/docs
      -> deterministic acceptance
      -> real runtime/test/build validation
      -> failure-specific repair
      -> package only after clean verification

KEY CHANGES
-----------
1. CONTRACTS BEFORE CODE
   Each planned file now declares:
     - phase
     - exact depends_on project paths
     - public exports
     - concise class/function/method signatures
   Project-wide architecture rules and shared data contracts are also frozen before implementation.

2. VISIBLE SKELETON-FIRST REPOSITORY
   Jarvis immediately materializes importable intermediate source shells for planned source modules.
   The project folder therefore shows its intended repository shape quickly instead of staying nearly empty
   while Qwen spends many minutes on the first large file.

3. DEPENDENCY-ORDERED IMPLEMENTATION
   Jarvis topologically orders files. Providers are implemented before their callers. The normal order is:
   foundation -> data -> service -> UI -> integration/entrypoint -> tests -> docs.

4. REAL DEPENDENCIES ARE INCLUDED AGAIN
   V32 normally used one outer generation attempt, but its "final attempt drops related context" rule meant
   that the only attempt could accidentally omit complete related files. V33 fixes that: a single normal
   attempt includes implemented dependency files plus the compact architecture/API indexes.

5. SMALLER, FOCUSED MODULES
   The architecture prompt targets roughly 240-line modules and asks the planner to split responsibilities
   likely to exceed ~360 lines. The final gate does not reject a valid larger module solely for line count.

6. FAILURE-SPECIFIC REPAIR PROMPTS
   Generic "fix this file" prompts are replaced with explicit modes including:
     - MISSING_EXPORT_PROVIDER
     - CIRCULAR_IMPORT
     - CALL_SIGNATURE_CONTRACT
     - DATA_MODEL_CONTRACT
     - FAILING_TEST
     - RUNTIME_TRACEBACK_ROOT_CAUSE
     - IMPLEMENT_CONTRACT_SKELETON
   Repairs are instructed to make the smallest change that advances the actual validator while preserving
   unrelated working behavior and public APIs.

7. DETERMINISTIC RUNTIME DIAGNOSIS FIRST
   If Jarvis already knows the provider/traceback owner, V33 skips an unnecessary Qwen diagnosis round-trip
   and goes directly to the proven target. Qwen diagnosis is reserved for genuinely ambiguous/missing-file cases.

8. INCREMENTAL BUILD STATUS
   Diagnostic workspaces contain JARVIS_V33_BUILD_STATUS.json and JARVIS_V33_ARCHITECTURE.json while building.
   They record planned/implemented/skeleton counts and visible/committed source bytes. These internal files are
   omitted from completed project ZIPs.

RUNTIME / CONTEXT
-----------------
V33 keeps the V32 Qwen3.5 native-context throughput profile. The server can expose 262,144 native tokens while
routine prompts use focused working windows. V33 improves architecture/context selection rather than blindly
stuffing the full 262K into every call.

The Qwen3.5 model remains the default local coding model.
