import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import tailwindConfig from "../tailwind.config.js";

const sourceRoot = path.dirname(fileURLToPath(import.meta.url));
const readSource = (...segments) =>
  fs.readFileSync(path.join(sourceRoot, ...segments), "utf8");

const collectCssFiles = (directory) => {
  const files = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...collectCssFiles(fullPath));
    else if (entry.isFile() && entry.name.endsWith(".css")) files.push(fullPath);
  }
  return files;
};

test("dark utilities follow Weave's selected theme instead of the device theme", () => {
  assert.deepEqual(tailwindConfig.darkMode, [
    "selector",
    '[data-theme="dark"]',
  ]);

  for (const cssFile of collectCssFiles(sourceRoot)) {
    const css = fs.readFileSync(cssFile, "utf8");
    assert.doesNotMatch(
      css,
      /@media\s*\(prefers-color-scheme:\s*dark\)/,
      `${path.relative(sourceRoot, cssFile)} must use the application theme selector`,
    );
  }
});

test("shared badge variants define contrasting backgrounds and text in both themes", () => {
  const badge = readSource("components", "ui", "Badge.jsx");

  const expectedPairs = [
    ["default", "bg-slate-100", "text-slate-700", "dark:bg-slate-800/90", "dark:text-slate-100"],
    ["info", "bg-blue-100", "text-blue-900", "dark:bg-blue-950/65", "dark:text-blue-100"],
    ["primary", "bg-blue-100", "text-blue-900", "dark:bg-blue-950/65", "dark:text-blue-100"],
    ["accent", "bg-indigo-100", "text-indigo-900", "dark:bg-indigo-950/65", "dark:text-indigo-100"],
    ["success", "bg-emerald-100", "text-emerald-900", "dark:bg-emerald-950/65", "dark:text-emerald-100"],
    ["warning", "bg-amber-100", "text-amber-950", "dark:bg-amber-950/65", "dark:text-amber-100"],
    ["error", "bg-rose-100", "text-rose-900", "dark:bg-rose-950/65", "dark:text-rose-100"],
  ];

  for (const [variant, ...classes] of expectedPairs) {
    assert.match(badge, new RegExp(`${variant}:`));
    for (const className of classes) assert.ok(badge.includes(className));
  }
});

test("semantic information surfaces have generated Tailwind colors", () => {
  assert.equal(tailwindConfig.theme.extend.colors.info.DEFAULT, "#2563EB");
  assert.equal(tailwindConfig.theme.extend.colors.info.soft, "#DBEAFE");
});
