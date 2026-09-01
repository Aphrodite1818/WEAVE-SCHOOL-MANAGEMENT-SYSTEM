import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("academic workflow navigation uses one labeled grid across breakpoints", async () => {
  const shell = await read(
    "src/features/academic-admin/AcademicWorkflowShell.jsx",
  );
  const navigator = await read(
    "src/features/academic-admin/AcademicOrbitNavigator.jsx",
  );

  assert.match(shell, /data-academic-workflow-switcher="true"/);
  assert.match(shell, /overflow-x-auto/);
  assert.match(shell, /w-max min-w-full gap-2/);
  assert.match(shell, /shrink-0 whitespace-nowrap/);
  assert.match(shell, /px-3 py-2/);
  assert.match(shell, /AcademicOrbitNavigator/);
  assert.doesNotMatch(shell, /SearchableSelect/);

  assert.match(navigator, /data-academic-workflow-navigator="true"/);
  assert.match(navigator, /data-academic-workflow-menu="true"/);
  assert.match(navigator, /grid grid-cols-3 gap-2/);
  assert.match(navigator, /academicWorkflowOrder\.map/);
  assert.match(navigator, /config\.shortTitle \|\| config\.title/);
  assert.match(navigator, /Open academic navigation/);
  assert.doesNotMatch(navigator, /orbitPosition/);
  assert.doesNotMatch(navigator, /Math\.cos/);
  assert.doesNotMatch(navigator, /h-\[22rem\] w-\[22rem\]/);
});

test("academic mobile workspace reserves installed-PWA bottom navigation space", async () => {
  const source = await read("src/styles/pwaInteractions.css");

  assert.match(source, /data-academic-workflow-navigator="true"/);
  assert.match(
    source,
    /html\[data-standalone-pwa="true"\] \[data-academic-workflow-navigator="true"\]/,
  );
  assert.match(source, /6\.25rem \+ env\(safe-area-inset-bottom\)/);
  assert.match(source, /#dashboard-content/);
  assert.match(source, /7\.5rem \+ env\(safe-area-inset-bottom\)/);
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
