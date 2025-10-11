# Pull Request Title
Short, descriptive title: e.g. `feat(explain-agent): scaffold ExplainAgent and llm_client`

## Summary
> What this PR changes, in one paragraph.

## Why
> Short rationale — why this change is needed.

## Changes
- Bullet list of files changed / added and a 1-line summary of each.

## How to test locally
1. Checkout branch: `git fetch && git checkout phaseB/devin-001-pr-template`
2. Run backend tests: `python -m unittest discover -s tests`  
   (or adjust command if repo uses other test commands)
3. For frontend: `cd frontend && npm ci && npm test` (if applicable)

## Checklist
- [ ] Unit tests added / updated (or existing tests pass)
- [ ] Linting passed (`flake8` / `eslint` as applicable)
- [ ] CI configured / tests run in PR
- [ ] Docs updated (if UI/behavior changed)
- [ ] Changelog entry (if feature)

## UI / Screenshots
- Add screenshot(s) or GIF(s) showing UI change (if any)

## Rollout plan
- How to deploy (one-liner). Include feature-flag notes if needed.

## Rollback
- Steps to revert if something goes wrong.

## Reviewer(s)
- Tag reviewers: @shravan (or specify team)
