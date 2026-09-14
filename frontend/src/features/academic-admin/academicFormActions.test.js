import assert from "node:assert/strict";
import test from "node:test";
import { dirname, resolve } from "node:path";
import { rm } from "node:fs/promises";
import react from "@vitejs/plugin-react";
import { createServer } from "vite";

let vite;
let FormActions;
const cacheDir = resolve(`.vite-test-cache-forms-${process.pid}`);
test.before(async () => {
  vite = await createServer({
    configFile: false,
    cacheDir,
    optimizeDeps: { noDiscovery: true, include: [] },
    plugins: [react()],
    server: { middlewareMode: true },
    appType: "custom",
    logLevel: "silent",
  });
  ({ FormActions } = await vite.ssrLoadModule("/src/features/academic-admin/AcademicWorkspacePrimitives.jsx"));
});
test.after(async () => {
  await vite?.close();
  // Only remove the temporary cache this test created inside its working directory.
  assert.equal(dirname(cacheDir), process.cwd());
  await rm(cacheDir, { recursive: true, force: true });
});

const buttons = (props) => FormActions(props).props.children.filter(Boolean);
test("create actions render separate native submit intents", () => {
  const actions = buttons({ repeatable: true });
  assert.equal(actions.length, 2);
  assert.equal(actions[0].props.children, "Save & add another");
  assert.equal(actions[0].props.value, "another");
  assert.equal(actions[1].props.children, "Save & close");
  assert.equal(actions[1].props.value, "close");
  assert.ok(actions.every((action) => action.props.type === "submit"));
});
test("editing has one save action and pending disables save and cancellation", () => {
  const actions = buttons({ repeatable: true, editing: true, onCancel() {} });
  assert.equal(actions.length, 2);
  assert.equal(actions[0].props.children, "Save changes");
  assert.equal(actions[1].props.type, "button");
  assert.ok(buttons({ repeatable: true, submitting: true, onCancel() {} }).every((action) => action.props.disabled));
});
