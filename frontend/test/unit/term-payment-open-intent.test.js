import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const testRoot = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(testRoot, "..", "..");
const readSource = (...segments) =>
  fs.readFileSync(path.join(frontendRoot, ...segments), "utf8");

test("pay-to-open term checkouts open the term after verified payment", () => {
  const academicSetup = readSource(
    "src",
    "features",
    "academic-admin",
    "AcademicSetupWorkspace.jsx",
  );
  const gettingStarted = readSource(
    "src",
    "pages",
    "admin",
    "AdminGettingStartedPage.jsx",
  );
  const billingPlans = readSource(
    "src",
    "pages",
    "admin",
    "SubscriptionOptionsPage.jsx",
  );
  const mobileBillingPlans = readSource(
    "src",
    "pages",
    "admin",
    "ResponsiveSubscriptionOptionsPage.jsx",
  );
  const verifyPage = readSource(
    "src",
    "pages",
    "admin",
    "SubscriptionVerifyPage.jsx",
  );
  const subscriptionService = readSource("src", "services", "subscriptionService.js");

  assert.match(academicSetup, /intent=open-term/);
  assert.match(academicSetup, /saveTermPaymentOpenIntent/);
  assert.match(academicSetup, /Compare all plans/);
  assert.match(gettingStarted, /admin\/getting-started\/\$\{step\.id\}/);
  assert.match(billingPlans, /postPaymentAction/);
  assert.match(billingPlans, /saveTermPaymentIntent/);
  assert.match(
    mobileBillingPlans,
    /export default ResponsiveSubscriptionOptionsPage/,
  );
  assert.match(subscriptionService, /TERM_PAYMENT_INTENT_KEY/);
  assert.match(subscriptionService, /sameTerm[\s\S]*sameReference/);
  assert.match(verifyPage, /consumeTermPaymentIntent/);
  assert.match(verifyPage, /academicService\.openTerm\(entitlement\.academic_term_id\)/);
  assert.match(verifyPage, /Payment verified and the academic term is now open\./);
});
