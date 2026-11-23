# Brand assets

Sources and tooling for the integration's brand images. The images Home Assistant
serves live in `custom_components/pi_hole_v6/brand/` (PNG only); the SVG sources
of the chosen design live in `docs/brand/source/`.

- `render.cjs` — SVG → PNG set (`NODE_PATH=$(npm root -g) node render.cjs <dir>`, needs Playwright).
- `preview.py` — light/dark comparison sheet of several proposals (needs Pillow).

Produced by the `ha-webdesigner` agent (`.claude/agents/ha-webdesigner.md`), which creates
`docs/brand/source/` for the design the user picks.
