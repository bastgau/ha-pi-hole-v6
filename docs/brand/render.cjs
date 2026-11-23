// Render SVG sources to the PNG set Home Assistant expects in `brand/`.
// Usage: NODE_PATH=$(npm root -g) node render.cjs <dir>
// <dir> holds icon.svg, logo.svg, logo-dark.svg (viewBox "0 0 W H").
// Output: icon.png (256) icon@2x.png (512) logo.png logo@2x.png dark_logo.png dark_logo@2x.png
const { chromium } = require("playwright");
const fs = require("node:fs");
const path = require("node:path");

const dir = process.argv[2];
if (!dir) throw new Error("usage: node render.cjs <dir>");

// [source svg, output name, scale relative to the SVG viewBox size]
const jobs = [
  ["icon.svg", "icon.png", 0.5],
  ["icon.svg", "icon@2x.png", 1],
  ["logo.svg", "logo.png", 1],
  ["logo.svg", "logo@2x.png", 2],
  ["logo-dark.svg", "dark_logo.png", 1],
  ["logo-dark.svg", "dark_logo@2x.png", 2],
];

(async () => {
  const browser = await chromium.launch();
  for (const [src, out, scale] of jobs) {
    const file = path.join(dir, src);
    if (!fs.existsSync(file)) continue;
    const svg = fs.readFileSync(file, "utf8");
    const [, w, h] = svg.match(/viewBox="0 0 (\d+) (\d+)"/);
    const page = await browser.newPage({
      viewport: { width: Math.round(w * scale), height: Math.round(h * scale) },
    });
    await page.setContent(
      `<style>html,body{margin:0;background:transparent}svg{display:block;width:100vw;height:100vh}</style>${svg}`,
    );
    // omitBackground keeps the PNG transparent
    fs.writeFileSync(
      path.join(dir, out),
      await page.screenshot({ omitBackground: true }),
    );
    await page.close();
  }
  await browser.close();
})();
