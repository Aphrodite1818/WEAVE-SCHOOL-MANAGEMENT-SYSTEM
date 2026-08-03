import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";


test("frontend bootstrap uses external scripts only", async () => {
  const html = await readFile(new URL("../index.html", import.meta.url), "utf8");
  const scriptTags = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)];

  assert.ok(scriptTags.length >= 2);
  for (const [, attributes, body] of scriptTags) {
    assert.match(attributes, /\bsrc=/i);
    assert.equal(body.trim(), "");
  }
});


test("Vercel deployment sets CSP, HSTS, and geolocation policy", async () => {
  const config = JSON.parse(
    await readFile(new URL("../vercel.json", import.meta.url), "utf8"),
  );
  const headers = Object.fromEntries(
    config.headers[0].headers.map(({ key, value }) => [key, value]),
  );

  assert.match(headers["Content-Security-Policy"], /script-src 'self'/);
  assert.doesNotMatch(headers["Content-Security-Policy"], /script-src[^;]*'unsafe-inline'/);
  assert.equal(headers["Strict-Transport-Security"], "max-age=31536000");
  assert.match(headers["Permissions-Policy"], /geolocation=\(self\)/);
});
