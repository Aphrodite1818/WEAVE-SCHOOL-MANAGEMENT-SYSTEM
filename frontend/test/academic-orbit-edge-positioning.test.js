import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const source = fs.readFileSync(
  new URL("../src/features/academic-admin/AcademicOrbitNavigator.jsx", import.meta.url),
  "utf8",
);

test("academic orbit launcher persists an edge-relative position", () => {
  assert.match(source, /weave:admin:academic-orbit-position:v1/);
  assert.match(source, /window\.localStorage\.getItem\(ORBIT_POSITION_STORAGE_KEY\)/);
  assert.match(source, /window\.localStorage\.setItem\(/);
  assert.match(source, /edge: parsed\.edge/);
  assert.match(source, /ratio: clamp\(parsed\.ratio, 0, 1\)/);
});

test("academic orbit launcher supports pointer dragging and nearest-edge snapping", () => {
  assert.match(source, /snapToNearestEdge/);
  assert.match(source, /onPointerDown=\{handlePointerDown\}/);
  assert.match(source, /onPointerMove=\{handlePointerMove\}/);
  assert.match(source, /onPointerUp=\{handlePointerUp\}/);
  assert.match(source, /onPointerCancel=\{handlePointerCancel\}/);
  assert.match(source, /DRAG_THRESHOLD/);

  for (const edge of ["left", "right", "top", "bottom"]) {
    assert.match(source, new RegExp(`edge: ["']${edge}["']`));
  }

  assert.doesNotMatch(
    source,
    /className=["'][^"']*fixed[^"']*bottom-4[^"']*right-3/,
  );
});

test("academic orbit reserves the installed PWA bottom navigation while positioning and dragging", () => {
  assert.match(source, /getBottomNavObstruction/);
  assert.match(source, /dataset\?\.standalonePwa !== "true"/);
  assert.match(source, /data-mobile-bottom-nav="true"/);
  assert.match(source, /getBoundingClientRect\(\)/);
  assert.match(source, /bottomObstruction/);
  assert.match(source, /getUsableViewportHeight/);
  assert.match(source, /window\.ResizeObserver/);
  assert.match(source, /orientationchange/);
});

test("academic orbit menu follows the selected edge without overflowing the usable viewport", () => {
  assert.match(source, /positionPreference\.edge === "right"/);
  assert.match(source, /positionPreference\.edge === "left"/);
  assert.match(source, /positionPreference\.edge === "top"/);
  assert.match(source, /viewport\.width - menuRect\.width - EDGE_GAP/);
  assert.match(source, /usableHeight - menuRect\.height - EDGE_GAP/);
  assert.match(source, /visibility: menuStyle \? "visible" : "hidden"/);
});
