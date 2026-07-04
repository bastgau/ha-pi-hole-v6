# Create pull request targeting main

Prepare and create a pull request from `develop` to `main`.

## Steps

1. The base branch is always `main`, the head branch is always `develop`
2. Run `git log main..develop --oneline` to list commits
3. Run `git diff main...develop --stat` to list changed files
4. Pick the most appropriate label from this list:
   - `pr:chore` — maintenance or tooling change
   - `pr:docs` — documentation
   - `pr:feat` — new feature
   - `pr:fix` — bug fix
   - `pr:refactor` — code refactoring
   - `pr:release` — release
   - `pr:style` — code style
   - `pr:test` — tests
5. The PR title is always `Release vX.Y.Z` where the version is determined by:
   - Running `git tag --sort=-version:refname | grep -v beta | head -1` to get the latest stable tag
   - Incrementing the minor version (e.g. `v0.3.0` → `v0.4.0`)
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
