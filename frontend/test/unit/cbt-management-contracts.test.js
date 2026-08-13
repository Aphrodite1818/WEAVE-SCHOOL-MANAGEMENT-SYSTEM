import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(__dirname, "../..");
const readSource = (relativePath) => readFile(path.join(frontendRoot, relativePath), "utf8");

test("CBT waiting flow confirms the exact setup challenge", async () => {
  const source = await readSource("src/services/cbtService.js");

  assert.match(source, /\/cbt\/pairing\/status/);
  assert.match(source, /status\.server_id/);
  assert.match(source, /status\?\.status === "expired"/);
  assert.match(source, /status\?\.status === "invalidated"/);
  assert.doesNotMatch(source, /existingServerIds/);
});

test("CBT inventory remains navigable when new pairing is unavailable", async () => {
  const provider = await readSource("src/features/subscriptions/SubscriptionProvider.jsx");
  const nav = await readSource("src/components/layout/navConfig.js");

  assert.match(provider, /MANAGEMENT_VISIBLE_FEATURES = new Set\(\["cbt_pairing"\]\)/);
  assert.match(nav, /\{ label: "CBT Servers", to: "\/admin\/cbt", icon: Cpu \}/);
  assert.doesNotMatch(nav, /CBT Servers[^\n]*featureCode/);
});
