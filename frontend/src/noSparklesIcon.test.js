import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));

function walk(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const fullPath = path.join(directory, entry.name);
    return entry.isDirectory() ? walk(fullPath) : [fullPath];
  });
}

test("frontend does not use the sparkle/star assistant icon", () => {
  const violations = walk(root)
    .filter((file) => /\.(js|jsx|ts|tsx)$/.test(file))
    .filter((file) => !file.endsWith("noSparklesIcon.test.js"))
    .filter((file) => fs.readFileSync(file, "utf8").includes("Sparkles"));
  assert.deepEqual(violations, []);
});
