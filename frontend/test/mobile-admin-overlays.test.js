import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("academic workflow navigation stays compact on mobile and uses the orbit launcher", async () => {
  const shell = await read(
    "src/features/academic-admin/AcademicWorkflowShell.jsx",
  );
  const orbit = await read(
    "src/features/academic-admin/AcademicOrbitNavigator.jsx",
  );

  assert.match(shell, /data-academic-workflow-switcher="true"/);
  assert.match(shell, /overflow-x-auto/);
  assert.match(shell, /min-w-max/);
  assert.match(shell, /AcademicOrbitNavigator/);
  assert.doesNotMatch(shell, /SearchableSelect/);

  assert.match(orbit, /grid-cols-3/);
  assert.match(orbit, /sm:hidden/);
  assert.match(orbit, /hidden h-\[22rem\] w-\[22rem\].*sm:block/);
  assert.match(orbit, /academicWorkflowOrder\.map/);
  assert.match(orbit, /Open academic navigation/);
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
