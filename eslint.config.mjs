// Minimal ESLint setup for the repository's JavaScript (a Lovelace card and its tests, if any): no package.json,
// no npm dependency in the repository.
// scripts/lint runs it through a pinned `npx eslint`. The config imports nothing, so the globals are declared by hand.

const browser = {
  CSS: "readonly",
  CustomEvent: "readonly",
  HTMLElement: "readonly",
  Image: "readonly",
  IntersectionObserver: "readonly",
  ResizeObserver: "readonly",
  ShadowRoot: "readonly",
  cancelAnimationFrame: "readonly",
  customElements: "readonly",
  document: "readonly",
  getComputedStyle: "readonly",
  history: "readonly",
  requestAnimationFrame: "readonly",
  window: "readonly",
};
const node = {
  console: "readonly",
  process: "readonly",
};

export default [
  { ignores: [".venv/**", "node_modules/**"] },
  {
    files: ["custom_components/**/*.js", "tests/**/*.mjs"],
    languageOptions: {
      ecmaVersion: 2024,
      sourceType: "module",
      globals: {
        // Available in the browser and in Node.
        Intl: "readonly",
        URL: "readonly",
        WeakMap: "readonly",
        globalThis: "readonly",
        setInterval: "readonly",
        clearInterval: "readonly",
        setTimeout: "readonly",
        clearTimeout: "readonly",
        structuredClone: "readonly",
        ...browser,
        ...node,
      },
    },
    linterOptions: { reportUnusedDisableDirectives: "error" },
    rules: {
      "no-undef": "error",
      "no-unused-vars": "error",
      "no-redeclare": "error",
      "no-var": "error",
      "prefer-const": "error",
      eqeqeq: "error",
      "no-shadow-restricted-names": "error",
      "no-dupe-keys": "error",
      "no-unreachable": "error",
      "no-self-assign": "error",
    },
  },
  {
    // A card that is a near-verbatim copy of an upstream file keeps its legacy style as it is, so the style-only
    // rules are off for this one file (the card named after the integration; inert when there is none).
    // The correctness rules stay on.
    files: ["custom_components/**/pi-hole-v6-card.js"],
    rules: {
      eqeqeq: "off",
      "prefer-const": "off",
      "no-var": "off",
      "no-unused-vars": "off",
    },
  },
];
