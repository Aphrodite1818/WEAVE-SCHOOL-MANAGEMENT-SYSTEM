import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const sourceRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const readSource = (...segments) =>
  fs.readFileSync(path.join(sourceRoot, ...segments), "utf8");

test("primary and sidebar controls use semantic readable foregrounds", () => {
  const button = readSource("components", "ui", "Button.jsx");
  const sidebar = readSource("components", "layout", "Sidebar.jsx");
  const contrastCss = readSource(
    "features",
    "tenant-branding",
    "brandingContrast.css",
  );

  assert.match(button, /from-primary\/90 to-primary text-primary-foreground/);
  assert.match(sidebar, /bg-sidebar-active text-sidebar-active-text/);
  assert.match(contrastCss, /--color-on-primary/);
  assert.match(contrastCss, /--color-on-accent/);
  assert.match(contrastCss, /--color-sidebar-active-text/);
  assert.match(contrastCss, /\.bg-primary\.text-white/);
  assert.match(contrastCss, /\.bg-primary\.text-text-inverse/);
});

test("workspace tour does not strip primary button backgrounds", () => {
  const css = readSource("components", "guides", "workspaceTour.css");

  assert.doesNotMatch(css, /\.workspace-tour button\s*\{[^}]*background-image:\s*none/);
  assert.match(
    css,
    /\.workspace-tour-close, \.workspace-tour-secondary-action, \.workspace-tour-dismiss-action \{ background-image: none; \}/,
  );
});
