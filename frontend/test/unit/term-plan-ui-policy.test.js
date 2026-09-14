import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const readSource = (relativePath) =>
  readFile(new URL(relativePath, import.meta.url), "utf8");

test("billing does not advertise scheduled or advance draft-term payment", async () => {
  const [billing, verification] = await Promise.all([
    readSource("../../src/pages/admin/BillingPage.jsx"),
    readSource("../../src/pages/admin/SubscriptionVerifyPage.jsx"),
  ]);

  assert.doesNotMatch(billing, /draft term is scheduled/i);
  assert.doesNotMatch(verification, /scheduled until that term opens/i);
  assert.match(
    billing,
    /Choose Free or a paid plan only when the next academic term is ready to open from Academic Terms/,
  );
  assert.match(
    billing,
    /If another term is still active, close it first/,
  );
});

test("term opening still preflights another active term before plan selection", async () => {
  const workspace = await readSource(
    "../../src/features/academic-admin/AcademicSetupWorkspace.jsx",
  );

  assert.match(workspace, /termOpenPreflightBlocker/);
  assert.match(workspace, /listTerms\(\{ is_current: true, limit: 100 \}\)/);
  assert.match(workspace, /if \(blocker\) \{[\s\S]*showError\(blocker\);[\s\S]*return;/);
});

test("backend keeps draft plan selection behind the current-term lifecycle", async () => {
  const source = await readSource(
    "../../../backend/app/modules/subscriptions/term_entitlement_service.py",
  );

  assert.match(source, /earlier_not_closed = \[/);
  assert.match(source, /active_other = \[/);
  assert.match(source, /if earlier_not_closed or active_other:/);
  assert.match(
    source,
    /This term is not ready for plan selection yet\. Finish the current or earlier term first\./,
  );
});
