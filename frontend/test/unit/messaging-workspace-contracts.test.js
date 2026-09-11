import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const readSource = (relativePath) =>
  readFile(new URL(`../../${relativePath}`, import.meta.url), "utf8");

test("messages workspace is wired to realtime message events", async () => {
  const [page, service] = await Promise.all([
    readSource("src/pages/shared/MessagesPage.jsx"),
    readSource("src/services/communicationService.js"),
  ]);

  assert.match(service, /"message\.created"/);
  assert.match(service, /"message\.read"/);
  assert.match(page, /realtimeClient\.subscribe\(MESSAGE_CREATED_EVENT/);
  assert.match(page, /realtimeClient\.subscribe\(MESSAGE_READ_EVENT/);
  assert.match(page, /playIncomingMessageSound/);
  assert.match(page, /messageService\s*\.\s*markRead/);
});

test("messages workspace exposes animated bubbles without call controls", async () => {
  const [page, styles] = await Promise.all([
    readSource("src/pages/shared/MessagesPage.jsx"),
    readSource("src/styles/messaging.css"),
  ]);

  assert.match(page, /weave-message-bubble/);
  assert.match(styles, /@keyframes weave-message-enter/);
  assert.match(styles, /prefers-reduced-motion/);
  assert.doesNotMatch(page, /PhoneCall|Video|Start call|Video call/);
});

test("communication navigation uses notices and exposes received notice routes", async () => {
  const [nav, studentRoutes, parentRoutes] = await Promise.all([
    readSource("src/components/layout/navConfig.js"),
    readSource("src/routes/studentRoutes.jsx"),
    readSource("src/routes/parentRoutes.jsx"),
  ]);

  assert.doesNotMatch(nav, /Announcements|\/announcements/);
  assert.match(nav, /\/admin\/notices/);
  assert.match(nav, /\/superadmin\/notices/);
  assert.match(nav, /\/teacher\/notices/);
  assert.match(nav, /\/student\/notices/);
  assert.match(nav, /\/parent\/notices/);
  assert.match(studentRoutes, /path="\/student\/notices"/);
  assert.match(parentRoutes, /path="\/parent\/notices"/);
});
