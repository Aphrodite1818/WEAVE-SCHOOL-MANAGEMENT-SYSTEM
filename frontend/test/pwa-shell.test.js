import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("the installed bottom navigation never cancels page touch movement", async () => {
  const source = await read("src/components/layout/BottomNav.jsx");

  assert.doesNotMatch(source, /onTouchMove\s*=/);
  assert.doesNotMatch(source, /\btouch-none\b/);
  assert.doesNotMatch(source, /\boverscroll-none\b/);
  assert.match(source, /data-mobile-bottom-nav="true"/);
});

test("standalone PWA scrolling and dock geometry have one final authority", async () => {
  const [pwaCss, directoryCss, mainSource] = await Promise.all([
    read("src/styles/pwaInteractions.css"),
    read("src/styles/mobileDirectoryCards.css"),
    read("src/main.jsx"),
  ]);

  assert.match(
    pwaCss,
    /data-mobile-bottom-nav="true"[\s\S]*?position:\s*fixed\s*!important/,
  );
  assert.match(pwaCss, /transform:\s*translate3d\(0, 0, 0\)\s*!important/);
  assert.match(
    pwaCss,
    /#dashboard-scroll-viewport[\s\S]*?overflow-y:\s*auto\s*!important/,
  );
  assert.match(pwaCss, /touch-action:\s*pan-y pinch-zoom\s*!important/);
  assert.doesNotMatch(
    directoryCss,
    /data-mobile-bottom-nav="true"[\s\S]*?position:\s*absolute\s*!important/,
  );

  const dashboardIndex = mainSource.indexOf("./styles/mobileDashboard.css");
  const directoryIndex = mainSource.indexOf("./styles/mobileDirectoryCards.css");
  const pwaIndex = mainSource.indexOf("./styles/pwaInteractions.css");
  assert.ok(dashboardIndex >= 0 && directoryIndex >= 0 && pwaIndex >= 0);
  assert.ok(pwaIndex > dashboardIndex && pwaIndex > directoryIndex);
});

test("Android and iOS receive installable PNG app metadata", async () => {
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
        icon.type === "image/png" &&
        icon.sizes === "192x192" &&
        icon.purpose === "any",
    ),
  );
  assert.ok(
    manifest.icons.some(
      (icon) =>
        icon.type === "image/png" &&
        icon.sizes === "512x512" &&
        icon.purpose === "any",
    ),
  );
  assert.ok(
    manifest.icons.some(
      (icon) =>
        icon.type === "image/png" &&
        icon.sizes === "512x512" &&
        icon.purpose === "maskable",
    ),
  );
  assert.match(html, /rel="manifest"[^>]+manifest\.json/);
  assert.match(html, /rel="apple-touch-icon"[^>]+weave-192\.png/);
  assert.match(html, /rel="icon"[^>]+image\/png[^>]+weave-192\.png/);
  assert.match(html, /name="mobile-web-app-capable" content="yes"/);
  assert.match(html, /name="apple-mobile-web-app-capable" content="yes"/);
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
        header.key === "Content-Type" &&
        header.value.startsWith("application/manifest+json"),
    ),
  );
  assert.ok(
    serviceWorkerHeaders.headers.some(
      (header) =>
        header.key === "Service-Worker-Allowed" && header.value === "/",
    ),
  );
});
