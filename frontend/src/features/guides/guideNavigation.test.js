import assert from "node:assert/strict";
import test from "node:test";

import { clearGuideReturn, readGuideReturn, saveGuideReturn } from "./guideNavigation.js";

function installWindow() {
  const values = new Map();
  globalThis.window = {
    sessionStorage: {
      getItem: (key) => values.get(key) ?? null,
      setItem: (key, value) => values.set(key, value),
      removeItem: (key) => values.delete(key),
    },
  };
  return values;
}

test("guide return state persists and clears", () => {
  installWindow();
  saveGuideReturn({ role: "teacher", route: "/teacher/getting-started", stepId: "results" });
  assert.deepEqual(readGuideReturn(), {
    role: "teacher",
    route: "/teacher/getting-started",
    stepId: "results",
  });
  clearGuideReturn();
  assert.equal(readGuideReturn(), null);
  delete globalThis.window;
});