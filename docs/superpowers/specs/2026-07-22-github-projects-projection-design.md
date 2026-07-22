# GitHub Projects Projection and Label Policy Design

## Goal

Project Truss will support optional GitHub Projects v2 membership through the native GitHub CLI. It will also distinguish descriptive repository labels from lifecycle labels. GitHub issues, relationships, pull requests, CI, Git, and worktrees will remain the lifecycle sources of truth.

## Product contract

Project Truss must not create, require, or interpret labels such as `ready`, `claimed`, `blocked`, or `done` as lifecycle state. The lifecycle policy will continue to derive those states from current provider and repository evidence.

Project Truss will preserve labels already attached to an issue. A caller may request descriptive or taxonomy labels such as `bug`, `area:cli`, or `priority:high`. Shape may add those requested labels, then re-read the issue to verify them. Shape must not remove unrelated labels or translate lifecycle state into labels.

A caller may request Project membership by supplying an explicit project owner and project number. Project Truss will not discover a default Project, create a Project, or require Project membership for outcomes that omit this target.

The selected Project will serve as a membership view. Project Truss will add the outcome root, leaf issues, and linked pull requests. It will not create or change Status values, custom fields, views, workflows, or automation. Project fields will not affect lifecycle derivation.

## Durable project target

Shape will preflight the supplied owner and number with `gh project view PROJECT_NUMBER --owner OWNER --format json`. The returned canonical Project URL will identify the target.

Shape will record exactly one `GitHub Project projection: CANONICAL_URL` line in the outcome root issue under the existing `Constraints, risks, and authority` heading. A single-leaf outcome uses its leaf as the root. A multi-leaf outcome uses the parent issue. This location gives later sessions one durable GitHub source for the projection target without adding a configuration file or contract heading.

Deliver will re-read the root issue before adding a pull request. It will reject a malformed, inaccessible, or conflicting target instead of guessing.

## Native GitHub CLI flow

Project Truss will use official `gh project` commands as its required interface. The `gh projects` extension may remain installed and available for manual use, but Project Truss will not depend on it.

For a requested Project target, Shape will:

1. Confirm that `gh` and the `gh project` command exist.
2. Run `gh project view PROJECT_NUMBER --owner OWNER --format json` to verify access and capture the canonical URL.
3. Create each issue with the existing six-section contract. Shape may pass caller-requested descriptive labels to `gh issue create`.
4. Re-read issue labels and preserve labels that Project Truss did not add.
5. Check current Project membership by URL through structured `gh project item-list PROJECT_NUMBER --owner OWNER --format json --limit 1000` output.
6. Add a missing issue with `gh project item-add PROJECT_NUMBER --owner OWNER --url ISSUE_URL --format json`.
7. Re-read membership and require one matching item URL.

Deliver will repeat the membership check for the linked pull request and add a missing PR with the same `item-add` command. Close will re-check the configured issue and PR memberships as acceptance evidence. Membership checks must detect truncated item listings from the structured result and use a larger explicit limit or a focused native `gh api graphql` query before reporting absence.

The pre-read and post-read make repeated runs idempotent. Project Truss will not remove Project items during normal lifecycle cleanup because the Project owner controls that view.

## State and failure handling

`derive_state` and `OutcomeSnapshot` will remain unchanged. Project membership, Project Status, and Project custom fields will not become lifecycle inputs.

Project Truss will use the existing `github_capability_missing` blocker when a requested projection cannot proceed because:

- the installed `gh` lacks native Project commands;
- the authenticated account cannot access the selected Project;
- the credential lacks the `project` OAuth scope;
- structured output is missing or truncated without a safe focused fallback;
- a membership mutation or verification fails; or
- the durable Project URL conflicts with the caller-supplied target.

The blocker applies to the requested Shape, Deliver, or Close operation. Work that did not request Project membership will retain current behavior.

Project Truss will report the failed command category and safe remediation. It will not run `gh auth refresh` without user approval. The supported remediation for a missing scope is `gh auth refresh -h github.com -s project`.

## Authority and security

Adding labels, changing an issue body, adding a Project item, and refreshing OAuth scopes mutate external state or credentials. Existing explicit scope may authorize routine issue and Project membership writes. Project Truss must ask through `advanced-user-input` when that authority is absent.

Project Truss must request separate approval before refreshing OAuth scopes. It must not display credentials or invoke commands that print a token.

## Repository changes

The implementation will update:

- `README.md` and `docs/project-truss/README.md` for the public contract and CLI prerequisites;
- `skills/shape/SKILL.md` for descriptive labels, Project preflight, issue membership, and verification;
- `skills/deliver/SKILL.md` for pull-request membership;
- `skills/close/SKILL.md` for final membership verification; and
- focused tests that protect the installable skill surface.

The implementation will not add a Python Projects adapter, a repository Project configuration file, a new contract heading, or Project fields to the lifecycle snapshot.

## Verification

Behavior-level source tests will require:

- explicit permission for descriptive labels and rejection of lifecycle labels;
- preservation of existing issue labels;
- explicit project owner and number selection;
- native `gh project view`, `item-add`, and structured `item-list` commands;
- issue and pull-request membership verification;
- no required `gh projects` extension; and
- no Project input to lifecycle derivation.

The existing lifecycle tests will continue to prove Ready, Claimed, In review, Blocked, and Done from issue, relationship, pull-request, CI, and repository evidence.

Validation will run targeted tests, then `./scripts/validate.sh`. Live CLI checks will verify the installed native commands and authentication. A membership mutation requires an approved Project target and the `project` OAuth scope.

Changes to skills and runtime documentation modify the installable surface. Completion therefore requires the repository post-revision loop: commit the intended source changes, sync the live source with validation, register the plugin, verify the current version banner, run cleanup, inspect final Git status, and tell the user to start a fresh Codex session.
