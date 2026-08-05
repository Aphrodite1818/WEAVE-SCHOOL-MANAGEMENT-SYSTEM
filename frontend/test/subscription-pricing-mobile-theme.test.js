import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("subscription pricing is hydrated from the public backend catalogue", async () => {
  const service = await read("src/services/subscriptionService.js");
  const runtime = await read(
    "src/features/subscriptions/pricingCatalogueRuntime.js",
  );
  const main = await read("src/main.jsx");

  assert.match(service, /getPublicPlans/);
  assert.match(service, /\/subscriptions\/plans/);
  assert.match(service, /auth: false/);
  assert.match(runtime, /Pricing unavailable/);
  assert.match(runtime, /backendPlan\.amount/);
  assert.match(runtime, /backendPlan\.features/);
  assert.match(runtime, /backendPlan\.limits/);
  assert.match(main, /subscriptionService\s*\.getPublicPlans\(\)/);
  assert.match(main, /applyPublicPricingCatalogue/);
});

test("iOS PWA nav and billing dock fixes do not target Android", async () => {
  const css = await read("src/styles/mobilePlatformFixes.css");

  assert.match(css, /data-pwa-platform="ios"/);
  assert.match(css, /bottom: -0\.35rem/);
  assert.match(css, /data-mobile-billing-action/);
  assert.match(css, /position: fixed/);
  assert.match(css, /safe-area-inset-top/);
  assert.doesNotMatch(css, /data-pwa-platform="android"[\s\S]*bottom:/);
});

test("theme chrome follows the resolved application theme", async () => {
  const source = await read("src/utils/themeChromeSync.js");

  assert.match(source, /style\.colorScheme/);
  assert.match(source, /meta\[name="theme-color"\]/);
  assert.match(source, /meta\[name="color-scheme"\]/);
  assert.match(source, /MutationObserver/);
  assert.match(source, /weave:accessibility-preferences-changed/);
});

test("mobile browser chrome refreshes without changing installed PWA behavior", async () => {
  const runtime = await read("src/utils/themeChromeSync.js");
  const startup = await read("public/theme-init.js");
  const html = await read("index.html");

  assert.match(runtime, /display-mode: standalone/);
  assert.match(runtime, /data-weave-browser-theme/);
  assert.match(runtime, /requestAnimationFrame/);
  assert.match(runtime, /BROWSER_THEME_RECHECK_DELAY_MS/);
  assert.match(runtime, /pageshow/);
  assert.match(startup, /data-weave-browser-theme/);
  assert.match(startup, /media: "all"/);
  assert.match(startup, /media: "not all"/);
  assert.doesNotMatch(
    html,
    /<meta name="theme-color" content="#0F172A"\s*\/>/,
  );
  assert.ok(
    html.indexOf('<script src="/theme-init.js"></script>') <
      html.indexOf('<link rel="manifest"'),
  );
});
