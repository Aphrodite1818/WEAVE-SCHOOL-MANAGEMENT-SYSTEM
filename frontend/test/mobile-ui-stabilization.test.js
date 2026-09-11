import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("dashboard mobile spacing is controlled by shared, page-safe selectors", async () => {
  const css = await read("src/styles/mobileDashboard.css");

  assert.match(css, /#dashboard-content \{[\s\S]*?gap:\s*1rem/);
  assert.match(css, /padding-left:\s*clamp\(0\.75rem, 3\.5vw, 1rem\)/);
  assert.match(css, /#dashboard-content \.card-base,[\s\S]*?border-radius:\s*1rem/);
  assert.doesNotMatch(css, /#dashboard-content\s*>\s*div\s*>\s*div:first-child/);
  assert.doesNotMatch(css, /width:\s*calc\(100% \+ 1\.25rem\)/);
});

test("mobile records use natural page scrolling and readable single-column rows", async () => {
  const [dashboardCss, directoryCss] = await Promise.all([
    read("src/styles/mobileDashboard.css"),
    read("src/styles/mobileDirectoryCards.css"),
  ]);

  assert.match(
    dashboardCss,
    /#dashboard-content \.mobile-scroll-list \{[\s\S]*?max-height:\s*none;[\s\S]*?overflow:\s*visible/,
  );
  assert.match(
    dashboardCss,
    /mobile-scroll-list\.record-list-grid,[\s\S]*?grid-template-columns:\s*minmax\(0, 1fr\)/,
  );
  assert.match(
    directoryCss,
    /\.directory-card-grid\.mobile-scroll-list \{[\s\S]*?max-height:\s*none;[\s\S]*?overflow-y:\s*visible\s*!important/,
  );
  assert.doesNotMatch(directoryCss, /calc\(100dvh - 18rem/);
});

test("shared mobile actions and dialogs expose comfortable touch layouts", async () => {
  const [dashboardCss, primitives, pageHeader, modal] = await Promise.all([
    read("src/styles/mobileDashboard.css"),
    read("src/components/dashboard/DashboardPrimitives.jsx"),
    read("src/components/shared/PageHeader.jsx"),
    read("src/components/ui/Modal.jsx"),
  ]);

  assert.match(dashboardCss, /#dashboard-content \.btn-base \{\s*min-height:\s*2\.75rem/);
  assert.match(dashboardCss, /#dashboard-content \.page-header-actions[\s\S]*?width:\s*100%/);
  assert.match(primitives, /dashboard-section-action/);
  assert.match(pageHeader, /className="page-header/);
  assert.match(pageHeader, /className="page-header-actions"/);
  assert.match(modal, /items-end px-0 pb-0 pt-3 backdrop-blur-sm sm:items-center/);
  assert.match(modal, /max-h-\[min\(90dvh,100%\)\] rounded-b-none/);
  assert.match(modal, /px-4 py-4[^"]*sm:px-5 sm:py-5/);
});

test("mobile dashboard KPIs retain the established two-column contract", async () => {
  const css = await read("src/styles/mobileDashboard.css");

  assert.match(
    css,
    /#dashboard-content \.stat-grid,\s*#dashboard-content \.dashboard-kpi-grid \{\s*grid-template-columns:\s*repeat\(2, minmax\(0, 1fr\)\)/,
  );
});

test("mobile workspace tour collision checks the full target rectangle", async () => {
  const tour = await read("src/components/guides/WorkspaceTour.jsx");

  assert.match(tour, /left < targetBox\.left \+ targetBox\.width/);
  assert.match(tour, /right > targetBox\.left/);
  assert.match(tour, /candidate\.top < targetBox\.top \+ targetBox\.height/);
  assert.match(tour, /bottom > targetBox\.top/);
});
