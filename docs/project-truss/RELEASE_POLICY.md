# Project Truss Release Policy

Project Truss uses a clean breaking identity. Version 1.0.0 has no compatibility alias for the predecessor namespace or its route model.

An installable revision is complete only after committed source passes `./scripts/validate.sh`, `./scripts/sync-live.sh --validate`, `codex plugin add project-truss@personal --json`, the current version banner, cleanup, and source-status inspection. A fresh Codex session is required before installed-product claims.

Repository rename and predecessor-package removal are separate external actions. Preserve the predecessor installed package until fresh-session Project Truss trials pass and explicit removal authority is confirmed.
