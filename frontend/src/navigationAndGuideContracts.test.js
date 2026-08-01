import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const sourceRoot = path.dirname(fileURLToPath(import.meta.url));
const readSource = (...segments) =>
  fs.readFileSync(path.join(sourceRoot, ...segments), "utf8");

test("installed mobile navigation stays close to the device bottom edge", () => {
  const css = readSource("styles", "mobileOverrides.css");

  assert.match(
    css,
    /bottom:\s*calc\(-0\.45\s*\*\s*env\(safe-area-inset-bottom\)\)\s*!important/,
  );
  assert.match(
    css,
    /calc\(env\(safe-area-inset-bottom\)\s*\*\s*0\.45\)/,
  );
});

test("assisted class-limit warning routes admins to a working checkout page", () => {
  const setupPage = readSource("pages", "admin", "AdminGettingStartedPage.jsx");
  const plansPage = readSource("pages", "admin", "SubscriptionOptionsPage.jsx");

  assert.match(setupPage, /detail\?\.reason === "resource_limit_reached"/);
  assert.match(setupPage, /actionLabel:\s*"Upgrade plan"/);
  assert.match(setupPage, /navigate\("\/admin\/billing\/plans"\)/);
  assert.match(plansPage, /initializeSubscriptionCheckout/);
  assert.match(plansPage, /window\.location\.assign\(response\.authorization_url\)/);
});

test("all guided setup exit actions return to the actor dashboard", () => {
  const adminGuide = readSource("pages", "admin", "AdminGettingStartedPage.jsx");
  const roleGuide = readSource("pages", "shared", "RoleGettingStartedPage.jsx");

  assert.match(adminGuide, /navigate\("\/admin\/dashboard", \{ replace: true \}\)/);
  assert.match(adminGuide, /onClick=\{\(\) => navigate\("\/admin\/dashboard"\)\}/);
  assert.match(roleGuide, /navigate\(guide\.config\.dashboardRoute, \{ replace: true \}\)/);
  assert.match(roleGuide, /onClick=\{\(\) => navigate\(guide\.config\.dashboardRoute\)\}/);
});
