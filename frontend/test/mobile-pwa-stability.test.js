import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("mobile PWA stability is initialized after the existing interaction styles", async () => {
  const mainSource = await read("src/main.jsx");

  const interactionStyleIndex = mainSource.indexOf("./styles/pwaInteractions.css");
  const stabilityStyleIndex = mainSource.indexOf("./styles/mobilePwaStability.css");

  assert.ok(interactionStyleIndex >= 0);
  assert.ok(stabilityStyleIndex > interactionStyleIndex);
  assert.match(mainSource, /installMobilePwaStability\(\)/);
});

test("the runtime separates platform, keyboard, and stable layout state", async () => {
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
});

test("pricing scroll regions are explicitly marked and horizontal state is reset", async () => {
  const source = await read("src/utils/mobilePwaStability.js");

  assert.match(source, /\/admin\/billing\/plans/);
  assert.match(source, /pricingCardCarousel/);
  assert.match(source, /pricingTabsScroll/);
  assert.match(source, /scrollTo\(\{[\s\S]*?left:\s*0/);
  assert.match(source, /MutationObserver/);
  assert.match(source, /pushState/);
  assert.match(source, /replaceState/);
});

test("platform offsets and keyboard compensation do not change the dock layout contract", async () => {
  const css = await read("src/styles/mobilePwaStability.css");

  assert.match(
    css,
    /data-pwa-platform="android"[\s\S]*?padding-bottom:\s*max\([\s\S]*?0\.5rem/,
  );
  assert.match(
    css,
    /data-pwa-platform="ios"[\s\S]*?calc\(env\(safe-area-inset-bottom, 0px\) - 1rem\)/,
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
    /data-mobile-bottom-nav="true"\]\s*>\s*div[\s\S]*?pointer-events:\s*auto/,
  );
});

test("the public shell is horizontally clipped while pricing regions remain swipeable", async () => {
  const css = await read("src/styles/mobilePwaStability.css");

  assert.match(css, /\.public-page-shell[\s\S]*?overflow-x:\s*clip\s*!important/);
  assert.match(
    css,
    /data-pricing-card-carousel="true"[\s\S]*?overflow-x:\s*auto\s*!important/,
  );
  assert.match(
    css,
    /data-pricing-card-carousel="true"[\s\S]*?overscroll-behavior-inline:\s*contain\s*!important/,
  );
  assert.match(
    css,
    /data-pricing-card-carousel="true"[\s\S]*?scroll-snap-type:\s*inline mandatory\s*!important/,
  );
});
