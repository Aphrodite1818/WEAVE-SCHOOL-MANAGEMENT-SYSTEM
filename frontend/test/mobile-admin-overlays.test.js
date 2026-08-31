import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("academic workflow tabs use a readable mobile grid and retain desktop scrolling", async () => {
  const source = await read(
    "src/features/academic-admin/AcademicWorkflowShell.jsx",
  );

  assert.match(source, /data-academic-workflow-switcher="true"/);
  assert.match(source, /grid-cols-2/);
  assert.match(source, /sm:flex/);
  assert.match(source, /sm:overflow-x-auto/);
  assert.match(source, /min-w-0 whitespace-normal break-words/);
  assert.match(source, /sm:min-w-max sm:shrink-0 sm:whitespace-nowrap/);
});

test("the shared modal stays centered inside the live visual viewport", async () => {
  const source = await read("src/components/ui/Modal.jsx");

  assert.match(source, /window\.visualViewport/);
  assert.match(source, /addEventListener\("resize", syncVisualViewport\)/);
  assert.match(source, /addEventListener\("scroll", syncVisualViewport\)/);
  assert.match(source, /data-modal-visual-viewport="true"/);
  assert.match(source, /justify-center/);
  assert.match(source, /placement === "bottom"/);
  assert.match(source, /items-end/);
  assert.match(source, /max-h-full/);
  assert.match(source, /data-modal-scroll-container="true"/);
  assert.match(source, /data-modal-footer="true"/);
  assert.match(source, /shrink-0 border-t/);
});

test("the modal fix does not modify bottom-navigation geometry", async () => {
  const source = await read("src/components/ui/Modal.jsx");

  assert.doesNotMatch(source, /data-mobile-bottom-nav/);
  assert.doesNotMatch(source, /--mobile-bottom-nav-clearance/);
  assert.doesNotMatch(source, /translate3d/);
});
