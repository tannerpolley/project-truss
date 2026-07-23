# Project Truss Release Policy

Project Truss 2.0 is a clean breaking release. It has no `deliver` alias and does not retain the v1 six-heading issue parser.

Existing unclaimed v1 issues must be reshaped. An active v1 claim may finish under v1 or be released and restarted under 2.0.

An installable revision is complete only after committed source passes `./scripts/validate.sh`, `./scripts/sync-live.sh --validate`, `codex plugin add project-truss@personal --json`, the current version banner, cleanup, and source-status inspection. A fresh Codex session is required before installed-product claims.

Repository rename and predecessor-package removal are separate external actions. Preserve the predecessor installed package until fresh-session Project Truss trials pass and explicit removal authority is confirmed.
