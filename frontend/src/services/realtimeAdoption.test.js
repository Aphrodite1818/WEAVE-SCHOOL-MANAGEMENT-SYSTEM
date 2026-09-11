import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  matchesBulkImportEvent,
  matchesCbtPairingEvent,
  matchesSessionProgressionEvent,
} from "./realtimeEventMatchers.js";
import {
  markConnectionReady,
  resetAuthenticationLifecycle,
} from "./realtimeClientState.js";

const source = (relativeUrl) =>
  readFileSync(new URL(relativeUrl, import.meta.url), "utf8");

test("domain event matchers ignore unrelated jobs, sessions, and pairing requests", () => {
  assert.equal(
    matchesBulkImportEvent("job-1", { data: { job_id: "job-1" } }),
    true,
  );
  assert.equal(
    matchesBulkImportEvent("job-1", { data: { job_id: "job-2" } }),
    false,
  );
  assert.equal(
    matchesSessionProgressionEvent("session-1", {
      data: { session_id: "session-1" },
    }),
    true,
  );
  assert.equal(
    matchesSessionProgressionEvent("session-1", {
      data: { session_id: "session-2" },
    }),
    false,
  );
  assert.equal(
    matchesCbtPairingEvent("pairing-1", {
      data: { pairing_request_id: "pairing-1" },
    }),
    true,
  );
  assert.equal(
    matchesCbtPairingEvent("pairing-1", {
      data: { pairing_request_id: "pairing-2" },
    }),
    false,
  );
});

test("server-state pages use realtime reconciliation and remove repeating polling", () => {
  const bulk = source("../pages/admin/BulkImportPage.jsx");
  const session = source(
    "../features/academic-admin/SessionLifecycleWorkspace.jsx",
  );
  const pairing = source("../pages/admin/CBTPairingCodePage.jsx");

  assert.match(bulk, /subscribeConnection/);
  assert.doesNotMatch(bulk, /setInterval\([\s\S]{0,200}loadJob/);
  assert.match(session, /subscribeConnection/);
  assert.doesNotMatch(session, /setInterval\([\s\S]{0,200}loadClosingWorkflow/);
  assert.match(pairing, /matchesCbtPairingEvent/);
  assert.doesNotMatch(pairing, /setInterval/);
});

test("notification subscribers reconcile on events and reconnect and return cleanup", () => {
  for (const relativeUrl of [
    "../components/layout/Topbar.jsx",
    "../pages/shared/CommunicationInboxPage.jsx",
  ]) {
    const contents = source(relativeUrl);
    assert.match(contents, /NOTIFICATION_REALTIME_EVENTS\.map/);
    assert.match(contents, /state\.status === "reconnected"/);
    assert.match(
      contents,
      /unsubscribers\.forEach\(\(unsubscribe\) => unsubscribe\(\)\)/,
    );
  }
});

test("a full logout makes the next authenticated socket ready, not reconnected", () => {
  const clientState = {
    authenticatedOnce: false,
    reconnectAttempt: 4,
    lastAuthenticatedToken: "first-token",
  };

  assert.equal(markConnectionReady(clientState), "ready");
  assert.equal(markConnectionReady(clientState), "reconnected");
  resetAuthenticationLifecycle(clientState);
  assert.equal(markConnectionReady(clientState), "ready");
  assert.equal(clientState.reconnectAttempt, 0);
  assert.equal(clientState.lastAuthenticatedToken, null);
});
