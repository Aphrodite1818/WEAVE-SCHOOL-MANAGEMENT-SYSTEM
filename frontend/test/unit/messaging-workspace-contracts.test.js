import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { runInNewContext } from "node:vm";
import { parse } from "espree";
import postcss from "postcss";

const readSource = (relativePath) =>
  readFile(new URL(`../../${relativePath}`, import.meta.url), "utf8");

test("mobile chat selection opens the thread and new chat returns to the people list", async () => {
  const page = await readSource("src/pages/shared/MessagesPage.jsx");
  const ast = parse(page, { ecmaVersion: "latest", sourceType: "module", ecmaFeatures: { jsx: true }, range: true });
  const component = ast.body.find((node) => node.type === "ExportDefaultDeclaration").declaration;
  const declarations = component.body.body.filter((node) => node.type === "VariableDeclaration").flatMap((node) => node.declarations);
  const state = {};
  const setters = ["MobileChatOpen", "SidebarMode", "SidebarSearch", "SidebarRole", "RecipientKey", "SelectedId", "Selected", "Body", "SendError"];
  const context = Object.fromEntries(setters.map((key) => [`set${key}`, (value) => { state[key] = value; }]));
  context.actorKeyFor = (person) => `${person.actor_type}:${person.actor_id}`;
  const call = (name, argument) => {
    const handler = declarations.find((node) => node.id.name === name).init;
    runInNewContext(`(${page.slice(...handler.range)})`, context)(argument);
  };
  call("chooseConversation", "conversation-1");
  assert.equal(state.MobileChatOpen, true);
  assert.equal(state.SelectedId, "conversation-1");
  call("startNewChat");
  assert.equal(state.MobileChatOpen, false);
  assert.equal(state.SidebarMode, "people");
  call("chooseRecipient", { actor_type: "teacher", actor_id: "teacher-1" });
  assert.equal(state.MobileChatOpen, true);
  assert.equal(state.RecipientKey, "teacher:teacher-1");
  assert.equal(state.SelectedId, "");
});

test("pane visibility rules apply only below the desktop breakpoint", async () => {
  const css = postcss.parse(await readSource("src/styles/messaging.css"));
  const hiddenPanes = [];
  css.walkDecls("display", (declaration) => {
    if (declaration.value !== "none" || !declaration.parent.selector.includes("data-mobile-chat-open")) return;
    hiddenPanes.push(declaration.parent.selector);
    assert.equal(declaration.parent.parent.name, "media");
    assert.equal(declaration.parent.parent.params, "(max-width: 1023px)");
  });
  assert.equal(hiddenPanes.length, 1);
  assert.match(hiddenPanes[0], /data-mobile-chat-open="false"\] > main/);
  assert.match(hiddenPanes[0], /data-mobile-chat-open="true"\] > aside/);
});

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
