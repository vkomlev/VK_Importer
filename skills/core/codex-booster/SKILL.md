---
name: codex-booster
description: "Operate and improve Codex within the Cursor-based booster environment: select Codex role usage, apply local skills, manage rollout to projects, and enforce answer/code quality loops. Use when configuring, auditing, or scaling Codex workflows across your project fleet."
---

# Codex Booster

## Workflow
1. Identify requested operation mode:
- `use`: run Codex on a concrete task with correct tier and skills.
- `configure`: adjust Codex instructions/skills/routing.
- `rollout`: distribute skills and docs to project fleet.
- `audit`: review consistency and quality loops.
2. Load project inventory from [references/fleet-map.md](references/fleet-map.md).
3. Select skills and routing strategy from [references/skill-catalog.md](references/skill-catalog.md).
4. For rollout, use [references/rollout-ops.md](references/rollout-ops.md).
5. Enforce Cursor-agent error loop: if Cursor mistakes are found, require logging and preventive updates (see [references/cursor-error-governance.md](references/cursor-error-governance.md)).
6. Enforce quality gate coverage balance: code quality + tests + critical UX/UI + specification clarity.
7. Run mandatory `Skill Packaging Preflight` for every created/updated skill before rollout or troubleshooting:
- parse `SKILL.md` frontmatter as valid YAML (`name`, `description` required);
- run `python <codex_home>/skills/.system/skill-creator/scripts/quick_validate.py <skill_dir>`;
- if UI visibility matters, ensure `agents/openai.yaml` exists and is consistent with `SKILL.md`.
8. Produce explicit commands, expected artifacts, and verification checklist.
9. If request depends on latest Codex/Cursor capabilities, verify with official docs before final guidance.

## Input Contract
- `Mode` (`use|configure|rollout|audit`)
- `Project` or `Fleet Scope`
- `Objective`
- `Constraints`

## Output Contract
- `Selected Mode`
- `Tier and Skill Routing`
- `Execution Steps`
- `Commands`
- `Expected Artifacts`
- `Verification`
- `Skill Packaging Checks`
- `Cursor Error Loop Actions`
- `UX and Spec Clarity Actions`
- `Follow-up Improvements`

## Quality Rules
- Keep steps deterministic and project-scoped.
- Use dry-run first for bulk rollout.
- Do not claim "latest feature" without verifying source/date.
- Prefer minimal change set with clear rollback path.
- Never close review/audit tasks with Cursor-agent mistakes left unlogged.
- Do not treat a review as complete if critical UX path and spec ambiguity were not assessed.
- Treat skill rollout as failed if YAML frontmatter cannot be parsed or `quick_validate.py` fails.
- If a skill is "not visible in UI", check `agents/openai.yaml` before cache/restart hypotheses.
