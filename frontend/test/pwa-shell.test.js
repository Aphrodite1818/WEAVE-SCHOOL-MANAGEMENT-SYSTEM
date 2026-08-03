import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");
const readBytes = (path) => readFile(new URL(`../${path}`, import.meta.url));

const readPngDimensions = (buffer) => {
  assert.deepEqual(
    [...buffer.subarray(0, 8)],
    [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a],
  );
  assert.equal(buffer.subarray(12, 16).toString("ascii"), "IHDR");
  return {
    width: buffer.readUInt32BE(16),
    height: buffer.readUInt32BE(20),
    bitDepth: buffer[24],
    colorType: buffer[25],
  };
};

test("the installed bottom navigation never cancels page touch movement", async () => {
  const source = await read("src/components/layout/BottomNav.jsx");

  assert.doesNotMatch(source, /onTouchMove\s*=/);
  assert.doesNotMatch(source, /\btouch-none\b/);
  assert.doesNotMatch(source, /\boverscroll-none\b/);
  assert.match(source, /data-mobile-bottom-nav="true"/);
});

test("standalone PWA scrolling and floating dock geometry have one final authority", async () => {
  const [stabilityCss, interactionCss, directoryCss, mainSource] = await Promise.all([
    read("src/styles/mobilePwaStability.css"),
    read("src/styles/pwaInteractions.css"),
    read("src/styles/mobileDirectoryCards.css"),
    read("src/main.jsx"),
  ]);

  assert.match(
    stabilityCss,
    /data-mobile-bottom-nav="true"[\s\S]*?position:\s*fixed\s*!important/,
  );
  assert.match(stabilityCss, /transform:\s*translate3d\(0, 0, 0\)\s*!important/);
  assert.match(
    stabilityCss,
    /data-mobile-bottom-nav="true"[\s\S]*?background:\s*transparent\s*!important/,
  );
  assert.match(
    stabilityCss,
    /data-mobile-bottom-nav="true"[\s\S]*?pointer-events:\s*none/,
  );
  assert.match(
    stabilityCss,
    /data-mobile-bottom-nav="true"\]\s*>\s*div[\s\S]*?pointer-events:\s*auto/,
  );
  assert.match(
    stabilityCss,
    /data-pwa-platform="ios"[\s\S]*?safe-area-inset-bottom, 0px\) - 1\.45rem/,
  );
  assert.match(
    stabilityCss,
    /#dashboard-scroll-viewport[\s\S]*?overflow-y:\s*auto\s*!important/,
  );
  assert.match(stabilityCss, /touch-action:\s*pan-y pinch-zoom\s*!important/);
  assert.doesNotMatch(
    interactionCss,
    /data-mobile-bottom-nav="true"[\s\S]*?position:\s*fixed/,
  );
  assert.doesNotMatch(
    directoryCss,
    /data-mobile-bottom-nav="true"[\s\S]*?position:\s*absolute\s*!important/,
  );

  const dashboardIndex = mainSource.indexOf("./styles/mobileDashboard.css");
  const directoryIndex = mainSource.indexOf("./styles/mobileDirectoryCards.css");
  const interactionIndex = mainSource.indexOf("./styles/pwaInteractions.css");
  const stabilityIndex = mainSource.indexOf("./styles/mobilePwaStability.css");
  assert.ok(
    dashboardIndex >= 0
      && directoryIndex >= 0
      && interactionIndex >= 0
      && stabilityIndex >= 0,
  );
  assert.ok(stabilityIndex > dashboardIndex && stabilityIndex > directoryIndex);
  assert.ok(stabilityIndex > interactionIndex);
});

test("Android and iOS receive versioned installable app metadata", async () => {
  const [manifestSource, html] = await Promise.all([
    read("public/manifest.json"),
    read("index.html"),
  ]);
  const manifest = JSON.parse(manifestSource);

  assert.equal(manifest.id, "/");
  assert.equal(manifest.start_url, "/");
  assert.equal(manifest.scope, "/");
  assert.equal(manifest.display, "standalone");
  assert.equal(manifest.prefer_related_applications, false);
  assert.ok(
    manifest.icons.some(
      (icon) =>
        icon.type === "image/png"
        && icon.sizes === "192x192"
        && icon.purpose === "any"
        && icon.src.includes("weave-pwa-3"),
    ),
  );
  assert.ok(
    manifest.icons.some(
      (icon) =>
        icon.type === "image/png"
        && icon.sizes === "512x512"
        && icon.purpose === "any"
        && icon.src.includes("weave-pwa-3"),
    ),
  );
  assert.ok(
    manifest.icons.some(
      (icon) =>
        icon.type === "image/png"
        && icon.sizes === "512x512"
        && icon.purpose === "maskable"
        && icon.src.includes("weave-pwa-3"),
    ),
  );
  assert.match(html, /rel="manifest"[^>]+manifest\.json\?v=weave-pwa-3/);
  assert.match(html, /rel="apple-touch-icon"[^>]+weave-180\.png\?v=weave-pwa-3/);
  assert.match(html, /rel="icon"[^>]+image\/png[^>]+weave-192\.png\?v=weave-pwa-3/);
  assert.match(html, /name="mobile-web-app-capable" content="yes"/);
  assert.match(html, /name="apple-mobile-web-app-capable" content="yes"/);
});

test("generated Android and iOS app icons are valid opaque PNGs", async () => {
  const expectedIcons = [
    ["public/icons/weave-180.png", 180],
    ["public/icons/weave-192.png", 192],
    ["public/icons/weave-512.png", 512],
    ["public/icons/weave-maskable-512.png", 512],
  ];

  for (const [path, expectedSize] of expectedIcons) {
    const dimensions = readPngDimensions(await readBytes(path));
    assert.equal(dimensions.width, expectedSize);
    assert.equal(dimensions.height, expectedSize);
    assert.equal(dimensions.bitDepth, 8);
    assert.equal(dimensions.colorType, 2);
  }
});

test("the service worker enables detection without caching or intercepting the app", async () => {
  const [mainSource, serviceWorker, vercelSource] = await Promise.all([
    read("src/main.jsx"),
    read("public/sw.js"),
    read("vercel.json"),
  ]);
  const vercelConfig = JSON.parse(vercelSource);

  assert.match(mainSource, /import\.meta\.env\.PROD/);
  assert.match(mainSource, /serviceWorker[\s\S]*?register\("\/sw\.js"/);
  assert.match(serviceWorker, /addEventListener\("install"/);
  assert.match(serviceWorker, /addEventListener\("activate"/);
  assert.match(serviceWorker, /addEventListener\("fetch"/);
  assert.doesNotMatch(serviceWorker, /respondWith\s*\(/);
  assert.doesNotMatch(serviceWorker, /caches\.open\s*\(/);

  const manifestHeaders = vercelConfig.headers.find(
    (entry) => entry.source === "/manifest.json",
  );
  const serviceWorkerHeaders = vercelConfig.headers.find(
    (entry) => entry.source === "/sw.js",
  );
  assert.ok(manifestHeaders);
  assert.ok(serviceWorkerHeaders);
  assert.ok(
    manifestHeaders.headers.some(
      (header) =>
        header.key === "Content-Type"
        && header.value.startsWith("application/manifest+json"),
    ),
  );
  assert.ok(
    serviceWorkerHeaders.headers.some(
      (header) =>
        header.key === "Service-Worker-Allowed" && header.value === "/",
    ),
  );
});
