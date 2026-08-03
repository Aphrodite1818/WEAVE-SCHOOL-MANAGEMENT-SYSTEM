import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("mobile PWA stability is initialized after the interaction-only styles", async () => {
  const mainSource = await read("src/main.jsx");

  const interactionStyleIndex = mainSource.indexOf("./styles/pwaInteractions.css");
  const stabilityStyleIndex = mainSource.indexOf("./styles/mobilePwaStability.css");

  assert.ok(interactionStyleIndex >= 0);
  assert.ok(stabilityStyleIndex > interactionStyleIndex);
  assert.match(mainSource, /installMobilePwaStability\(\)/);
});

test("the runtime separates platform, keyboard, and stable layout state without pricing DOM patching", async () => {
  const source = await read("src/utils/mobilePwaStability.js");

  assert.match(source, /dataset\.pwaPlatform/);
  assert.match(source, /dataset\.keyboardOpen/);
  assert.match(source, /--pwa-layout-height/);
  assert.match(source, /--virtual-keyboard-height/);
  assert.match(source, /visualViewport/);
  assert.match(source, /orientationchange/);
  assert.match(source, /visibilitychange/);
  assert.match(source, /focusin/);
  assert.match(source, /focusout/);
  assert.doesNotMatch(source, /pricingCardCarousel/);
  assert.doesNotMatch(source, /pricingTabsScroll/);
  assert.doesNotMatch(source, /MutationObserver/);
  assert.doesNotMatch(source, /pushState/);
  assert.doesNotMatch(source, /replaceState/);
});

test("iOS dock spacing is lower while Android keeps its existing safe-area contract", async () => {
  const css = await read("src/styles/mobilePwaStability.css");

  assert.match(
    css,
    /data-pwa-platform="android"[\s\S]*?padding-bottom:\s*max\([\s\S]*?0\.5rem/,
  );
  assert.match(
    css,
    /data-pwa-platform="ios"[\s\S]*?calc\(env\(safe-area-inset-bottom, 0px\) - 1\.45rem\)/,
  );
  assert.match(
    css,
    /data-keyboard-open="true"[\s\S]*?translate3d\([\s\S]*?var\(--virtual-keyboard-height\)/,
  );
  assert.match(
    css,
    /data-mobile-bottom-nav="true"[\s\S]*?position:\s*fixed\s*!important/,
  );
  assert.match(
    css,
    /data-modal-open="true"[\s\S]*?data-mobile-bottom-nav="true"[\s\S]*?visibility:\s*hidden\s*!important/,
  );
});

test("every actor dashboard receives shared navbar clearance", async () => {
  const css = await read("src/styles/mobilePwaStability.css");
  const routeFiles = [
    "src/routes/adminRoutes.jsx",
    "src/routes/teacherRoutes.jsx",
    "src/routes/studentRoutes.jsx",
    "src/routes/parentRoutes.jsx",
    "src/routes/superadminRoutes.jsx",
  ];

  assert.match(css, /--mobile-bottom-nav-clearance/);
  assert.match(
    css,
    /#dashboard-content[\s\S]*?padding-bottom:\s*var\(--mobile-bottom-nav-clearance\)\s*!important/,
  );
  assert.match(
    css,
    /#dashboard-scroll-viewport[\s\S]*?scroll-padding-bottom:\s*var\(--mobile-bottom-nav-clearance\)/,
  );

  for (const path of routeFiles) {
    const source = await read(path);
    assert.match(source, /DashboardShell/);
  }
});

test("the shared modal owns the screen and only its body scrolls", async () => {
  const [modalSource, css] = await Promise.all([
    read("src/components/ui/Modal.jsx"),
    read("src/styles/mobilePwaStability.css"),
  ]);

  assert.match(modalSource, /z-\[100\]/);
  assert.match(modalSource, /data-modal-panel="true"/);
  assert.match(modalSource, /data-modal-header="true"/);
  assert.match(modalSource, /data-modal-scroll-container="true"/);
  assert.match(modalSource, /data-modal-footer="true"/);
  assert.match(modalSource, /min-h-0 flex-1 overflow-y-auto/);
  assert.match(
    css,
    /data-modal-scroll-container="true"[\s\S]*?min-height:\s*0[\s\S]*?overflow-y:\s*auto\s*!important/,
  );
  assert.match(
    css,
    /data-modal-panel="true"[\s\S]*?display:\s*flex[\s\S]*?overflow:\s*hidden/,
  );
});

test("mobile billing is an explicit mobile-first view while desktop retains the existing page", async () => {
  const [routeSource, billingSource] = await Promise.all([
    read("src/routes/adminRoutes.jsx"),
    read("src/pages/admin/ResponsiveSubscriptionOptionsPage.jsx"),
  ]);

  assert.match(routeSource, /ResponsiveSubscriptionOptionsPage/);
  assert.match(billingSource, /MobileSubscriptionOptionsPage/);
  assert.match(billingSource, /SubscriptionOptionsPage/);
  assert.match(billingSource, /data-mobile-billing-page="true"/);
  assert.match(billingSource, /data-mobile-billing-action="true"/);
  assert.match(billingSource, /Everything included/);
  assert.match(billingSource, /Plan capacity/);
  assert.doesNotMatch(billingSource, /grid-flow-col/);
  assert.doesNotMatch(billingSource, /overflow-x-auto/);
});

test("superadmin bottom navigation has a valid verification route", async () => {
  const routes = await read("src/routes/superadminRoutes.jsx");
  assert.match(routes, /path="\/superadmin\/verification"/);
});
