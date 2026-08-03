const SERVICE_WORKER_VERSION = "weave-pwa-v2";

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

/*
 * Keep requests network-owned. This pass-through listener preserves normal
 * application behavior while allowing browsers to recognize the PWA shell.
 */
self.addEventListener("fetch", () => {});

self.addEventListener("message", (event) => {
  if (event.data === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

void SERVICE_WORKER_VERSION;
