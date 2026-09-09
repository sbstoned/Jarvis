Jarvis V42.61.0

Fixes a Windows resume/trial cloning crash where `.jarvis_shared_build_cache/cache/npm/_cacache`
was copied while npm was actively mutating the content-addressed cache. Disappearing cache blobs
raised WinError 3 and aborted project continuation.

Changes:
- resume ZIP import skips `.jarvis_shared_build_cache`
- resume/trial/checkpoint source cloning skips `.jarvis_shared_build_cache`
- accepted-trial pruning removes nested shared caches
- packaging prunes nested shared caches BEFORE creating the ZIP
- persistent/authored source copy failures remain strict
- V42.60 27B hardware-fit 40,960 runtime / 262,144 native-capability behavior preserved
- V42.58/59 connected functional convergence and adaptive model I/O preserved
