# Create pull request targeting develop

Prepare and create a pull request for the current branch.

## Steps

1. The base branch is always `develop`
2. Run `git log <base>..HEAD --oneline` to list commits
3. Run `git diff <base>...HEAD --stat` to list changed files
4. Pick the most appropriate label from this list:
   - `pr:chore` — maintenance or tooling change
   - `pr:docs` — documentation
   - `pr:feat` — new feature
   - `pr:fix` — bug fix
   - `pr:refactor` — code refactoring
   - `pr:release` — release
   - `pr:style` — code style
   - `pr:test` — tests
5. Suggest a PR title following the commitlint rules from `.commitlintrc.mjs`:
   - Format: `type: subject`
   - Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
   - No scope, subject in lowercase, between 15 and 100 characters, no trailing period
6. Write a PR body with the following format:

```
## Summary

<one sentence describing the overall goal of the PR>

- <bullet point per meaningful change>
```
8. Display a full summary to the user:
   - Title
   - Base branch → head branch
   - Assignee: bastgau
   - Label
   - Body preview
9. Ask the user to confirm before creating the PR
10. On confirmation, create the PR with `gh pr create` assigned to `bastgau` with the chosen label
