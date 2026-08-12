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

  assert.match(academicSetup, /title="Pay for term"/);
  assert.match(academicSetup, />Pay for term</);
  assert.match(academicSetup, /intent=open-term/);
  assert.match(academicSetup, /saveTermPaymentOpenIntent/);
  assert.match(gettingStarted, /intent=open-term/);
  assert.match(gettingStarted, /saveTermPaymentOpenIntent/);
  assert.match(billingPlans, /shouldOpenTermAfterPayment/);
  assert.match(billingPlans, /saveTermPaymentOpenIntent/);
  assert.match(mobileBillingPlans, /shouldOpenTermAfterPayment/);
  assert.match(mobileBillingPlans, /saveTermPaymentOpenIntent/);
  assert.match(subscriptionService, /TERM_PAYMENT_OPEN_INTENT_KEY/);
  assert.match(subscriptionService, /sameTerm[\s\S]*sameReference/);
  assert.match(verifyPage, /consumeTermPaymentOpenIntent/);
  assert.match(verifyPage, /academicService\.openTerm\(entitlement\.academic_term_id\)/);
  assert.match(verifyPage, /Payment verified\. Your academic term is now open\./);
});
