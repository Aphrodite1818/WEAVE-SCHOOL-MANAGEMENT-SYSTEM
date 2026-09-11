import assert from "node:assert/strict";
import test from "node:test";

import {
  parseSentrySampleRate,
  sanitizeSentryBreadcrumb,
  sanitizeSentryEvent,
} from "../../src/config/sentry.js";

test("sanitizeSentryEvent removes browser secrets and direct identifiers", () => {
  const event = {
    request: {
      url: "https://weave.example/students?token=secret#private",
      headers: {
        Authorization: "Bearer access-token",
        Cookie: "session=private",
        "X-Request-ID": "request-123",
      },
      data: {
        password: "password-value",
        student_name: "Private Student",
      },
      query_string: "token=secret",
    },
    user: {
      id: "user-123",
      email: "private@example.com",
      ip_address: "127.0.0.1",
    },
    contexts: {
      auth: {
        refresh_token: "refresh-secret",
      },
      tenant: {
        tenant_id: "tenant-123",
      },
    },
  };

  const sanitized = sanitizeSentryEvent(event);
  const serialized = JSON.stringify(sanitized);

  assert.ok(sanitized);
  assert.doesNotMatch(serialized, /access-token/);
  assert.doesNotMatch(serialized, /session=private/);
  assert.doesNotMatch(serialized, /password-value/);
  assert.doesNotMatch(serialized, /Private Student/);
  assert.doesNotMatch(serialized, /private@example\.com/);
  assert.doesNotMatch(serialized, /127\.0\.0\.1/);
  assert.doesNotMatch(serialized, /refresh-secret/);
  assert.doesNotMatch(serialized, /token=secret/);
  assert.match(serialized, /request-123/);
  assert.match(serialized, /tenant-123/);
  assert.match(serialized, /user-123/);
});

test("sanitizeSentryBreadcrumb drops routine frontend noise", () => {
  assert.equal(
    sanitizeSentryBreadcrumb({ category: "console", message: "rendered" }),
    null,
  );
  assert.equal(
    sanitizeSentryBreadcrumb({ category: "navigation", message: "route" }),
    null,
  );
  assert.equal(
    sanitizeSentryBreadcrumb({
      category: "fetch",
      type: "http",
      data: {
        method: "GET",
        status_code: 200,
        url: "https://weave.example/api/v1/students?page=2&token=secret#private",
      },
    }),
    null,
  );
});

test("sanitizeSentryBreadcrumb keeps mutations and failed requests safely", () => {
  const mutation = sanitizeSentryBreadcrumb({
    category: "fetch",
    type: "http",
    data: {
      method: "POST",
      status_code: 201,
      url: "https://weave.example/api/v1/students?token=secret#private",
      authorization: "Bearer access-token",
      email: "private@example.com",
    },
  });
  const failedRead = sanitizeSentryBreadcrumb({
    category: "fetch",
    type: "http",
    data: {
      method: "GET",
      status_code: 500,
      url: "https://weave.example/api/v1/results?student=private",
    },
  });

  assert.ok(mutation);
  assert.ok(failedRead);
  assert.equal(mutation.data.authorization, "[Filtered]");
  assert.equal(mutation.data.email, "[Filtered]");
  assert.equal(mutation.data.url, "https://weave.example/api/v1/students");
  assert.equal(failedRead.data.url, "https://weave.example/api/v1/results");
});

test("parseSentrySampleRate rejects invalid values", () => {
  assert.equal(parseSentrySampleRate("0.5"), 0.5);
  assert.equal(parseSentrySampleRate("2", 1), 1);
  assert.equal(parseSentrySampleRate("invalid", 0.25), 0.25);
});
