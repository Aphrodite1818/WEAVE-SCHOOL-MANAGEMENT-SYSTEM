import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("billing quarantines late successful payments from effective term credit", async () => {
  const source = await read("src/pages/admin/BillingPage.jsx");

  assert.match(source, /paymentNeedsReconciliation/);
  assert.match(source, /payment\?\.reconciliation_required === true/);
  assert.match(source, /!paymentNeedsReconciliation\(payment\)/);
  assert.match(source, /Needs review/);
  assert.match(source, /Paid after checkout expiry/);
  assert.match(source, /does not count toward the term plan automatically/);
});

test("payment verification tells admins not to retry a reconciled late payment", async () => {
  const [router, verifyPage] = await Promise.all([
    read("../backend/app/modules/subscriptions/router.py"),
    read("src/pages/admin/SubscriptionVerifyPage.jsx"),
  ]);

  assert.match(router, /PAYMENT_RECONCILIATION_REQUIRED/);
  assert.match(router, /Do not retry payment/);
  assert.match(router, /settle_verified_term_payment/);
  assert.match(verifyPage, /PAYMENT_RECONCILIATION_REQUIRED/);
  assert.match(verifyPage, /Payment received — review required/);
  assert.match(verifyPage, /setSuccessRoute\("\/admin\/billing"\)/);
  assert.match(verifyPage, /Open billing/);
});
