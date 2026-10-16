export default {
  extends: ['@commitlint/config-conventional'],
  ignores: [(commit) => commit.includes('Signed-off-by: dependabot[bot]')],
  rules: {
    'type-case': [2, 'always', 'lowercase'],
    'type-enum': [
      2,
      'always',
      ['feat', 'fix', 'docs', 'style', 'refactor', 'test', 'chore']
    ],
    'type-empty': [2, 'never'],
    'subject-case': [2, 'always', 'lowercase'],
    'subject-empty': [2, 'never'],
    'subject-min-length': [2, 'always', 15],
    'subject-max-length': [2, 'always', 100],
    'subject-full-stop': [2, 'never', '.'],
    'body-empty': [2, 'always'],
    'footer-empty': [2, 'always']
  },
  parserPreset: {
    parserOpts: {
      headerPattern: /^([a-z]+(?:\|[a-z]+)*): (.*)$/,
      headerCorrespondence: ['type', 'subject']
    }
  }
};
