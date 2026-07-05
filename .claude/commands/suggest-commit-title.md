# Suggest commit title

Look at the staged files with `git diff --cached --name-only` and `git diff --cached --stat`. If there are no staged files, say so and stop - do not suggest a commit title.

Otherwise, suggest a commit title respecting these rules from `.commitlintrc.mjs`:

- Format: `type: subject`
- Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
- No scope
- Subject in lowercase
- Subject between 15 and 100 characters
- No trailing period
