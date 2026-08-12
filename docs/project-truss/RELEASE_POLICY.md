# Project Truss Release Policy

Project Truss 3.0 is a clean breaking release. It keeps the six public skills and does not retain the v2 issue parser as a compatibility path.

Existing application issues remain expressible through the application profile. Scientific work uses the v3 claim and evidence contracts.

An installable revision is complete only after committed source passes `./scripts/validate.sh`, `./scripts/sync-live.sh --validate`, `codex plugin add project-truss@personal --json`, the current version banner, cleanup, and source-status inspection. A fresh Codex session is required before installed-product claims.

Repository rename and predecessor-package removal are separate external actions. Preserve any predecessor installed package until explicit removal authority is confirmed.
