# Role assignment is vendor-neutral (permanent decision)

Status: accepted 2026-10-15. Applies to every Orchestrator workflow, project and campaign.

## Rule

Every compatible model, provider or agent tool is eligible for every workflow role: implementation, review, planning,
debugging, testing, coordination, and any role added later. Code must never encode "model X may only do role Y".
Models, providers, execution tools and roles stay four separate concepts:

| concept | what it is | examples |
|---|---|---|
| role | a job in a workflow (`^[a-z][a-z0-9_]{0,39}$`, open set) | `implementer`, `reviewer`, `deep_reviewer`, `planner`, `debugger`, `tester`, `coordinator` |
| profile | a model/provider configuration, opaque to the engine | `haiku`, `glm`, a codex profile |
| tool | the CLI that executes it | `codex`, `claude`, `gemini`, `agy`, `cursor`, `custom` |
| assignment | `{tool, profile}` bound to a role, with its `source` | |

The same assignment may hold every role, or different ones per role. Nothing is paired by default.

## Priority (per role)

1. **Explicit** assignment in the task prompt: `roles: {role: profile | {tool, profile, fallbacks}}`, or the older
   spellings `worker`, `worker_profile`, `workflow.reviewer_profile|reviewer_tool|deep_review_profile|deep_review_tool`.
   Stating one role twice with different values is `ROLE_CONFLICT`, never a silent pick.
2. **Hub-configured default** (`settings.json` in the data root, written by RPP `settings.apply`):
   `default_worker`, `default_worker_profile`, `default_reviewer_tool`, `default_reviewer_profile`, and
   `default_roles` (JSON, any role).
3. **Automatic recommendation**, only when `auto_assign` is on, from the candidates in `auto_pool`
   (JSON list of `{tool, profile}`). It never overrides 1 or 2 and is never required. How it works (`roles.recommend`):
   - capability filter: write roles (`implementer`, `debugger`) need a tool that can edit headlessly; read roles cannot
     use `custom`; unavailable or blocked candidates are listed under `excluded` with the reason;
   - ranking from this installation's own signed run evidence (`track_record.py`): smoothed completion rate of earlier
     write runs or review attempts per `(tool, profile)`, then a profile no other role uses (soft), then lower average
     tokens, then pool order;
   - fewer than 3 recorded runs for every candidate means **no evidence**: the first usable entry is taken and the
     stored `reason` says so (`basis: pool_order`, "not a measured recommendation"). Only `basis: history` is a ranking.
   The stored assignment carries `reason`, `basis`, the full `ranking` and `excluded`, so the choice can be audited.
   Not modelled: task difficulty, model quality beyond "completed", price per token, provider limits.

An unspecified `deep_reviewer` is the `reviewer` (stated inheritance). The resolved assignments and where each came
from (`explicit` / `hub_default` / `auto`) are stored in the signed request as `role_assignments`.

## Failure policy

- Never silently override an explicit selection. An unusable assignment (tool not installed, profile blocked) is
  `ROLE_UNAVAILABLE`; nothing is substituted unless that assignment lists its own `fallbacks` (the user's authorization).
- A needed role with no assignment from any source is `ROLE_UNASSIGNED`. The reviewer is checked before any paid step of
  the MAF workflow, so a missing reviewer costs nothing.
- Independent review is a *setting*, not a rule: `require_independent_review` (setting or `workflow` field) makes a
  reviewer that shares the implementer's profile `ROLE_INDEPENDENCE`; otherwise sharing is allowed and recorded in
  `role_notes`. `escalate_profile` (explicit user configuration) keeps its documented hand-over: the former implementer
  reviews the new one.
- `blocked_profiles` (default `mimo`, comma separated substrings) refuses whole profiles for every role. It is user
  editable configuration, not a model-to-role mapping.

## Tool neutrality of reviews

Reviews run through the assigned tool: `codex` keeps its read-only sandbox path; any other tool is run headless in an
empty evidence directory (the prompt carries the task, checks and diff). Their CLIs report no token usage, so usage is
recorded as UNKNOWN (never zero) and charged the assumed amount against lane budgets. Workers on `claude`/`gemini` get
only their file-edit approval flag; scope, acceptance and patch checks are unchanged.

## Code map

`roles.py` (resolution, validation, settings fields), `runner.create_task` (resolution at submission),
`maf_workflow._review_assignment` (availability check + fallbacks before work), `rpp.py` (settings schema),
private entry point `python -m respected_orchestrator roles` (dry-run of an assignment). Tests: `tests/workflows/test_roles.py`.

## Roles the engine consumes

- `implementer`, `reviewer`, `deep_reviewer`: every task / MAF workflow.
- `debugger`: when assigned, it executes the review-driven correction rounds (before any `escalate_profile` hand-over).
- `master`: the final master of a campaign/project review (`final.master`, or Hub `default_roles.master`; an explicit
  `final.command` wins, both together is `ROLE_CONFLICT`).
- `planner`: `python -m respected_orchestrator plan` drafts a project spec with the assigned tool (prompt carries the
  file list and chosen context files, no repository access), validates it with the engine, saves it under `drafts/`
  and never starts it.
- Representable but not consumed by any stage yet: `tester`, `coordinator`.

## Not covered (kept honest)

Hub's Orchestrator page still says role assignment cannot be edited there (Hub UI is outside this track); the
settings form does render the new fields because it is generated from the RPP schema.
