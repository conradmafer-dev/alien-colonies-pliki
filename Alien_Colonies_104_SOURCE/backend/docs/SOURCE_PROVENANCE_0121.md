# Alien Colonies 0.12.1: source provenance

This update is based on the actual production backend, not the older server
copies bundled with an Android export.

- Repository: `conradmafer-dev/pogranicze-serwer`.
- Base commit: `240875b37b6744a16c8f8b0cb096d3ed7b9fffb7`.
- Base Git tree: `01f1c527bab53456e11c758604bc8828f6031b31`.
- `main` and the latest successful Railway deployment matched this commit when
  checked on 16 October 2026.
- Railway deployment: `caee303a-f109-4d9a-a6fb-78ff94ee9022`, created
  14 October 2026 at 09:12 UTC, service `pogranicze-serwer`, domain
  `aliencolonies.com`.
- The complete baseline contains 3,471 tracked files. Every file was checked
  against its upstream Git blob identifier; the complete tree and original
  commit identifiers were also verified.
- The upstream tree contains no `AGENTS.md` instructions.

The production entry point is the repository-root `start_web.py`, which imports
`run.py`, `website.py` and the root `app.py`. The root `Dockerfile` and
`railway.toml` describe this deployment. Nested `server/` and `railway/` folders
are historical package copies and must not replace these root runtime files.

The Android client is maintained separately, starting from release 0.12.0,
version code 67. The older Godot client in this backend repository is not the
source of the new Android build.

The source discovery and local reconstruction did not change the production
service, its variables, player database or deployed commit. A local branch
`feature/galaxy-rings-inactivity` records the prepared update for review.
