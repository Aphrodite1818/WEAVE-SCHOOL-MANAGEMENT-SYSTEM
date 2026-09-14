import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const source = fs.readFileSync(
  new URL("../src/features/schoolCalendar/components/SchoolCalendarEventsWorkspace.jsx", import.meta.url),
  "utf8",
);

test("calendar events toolbar cannot force the academic workspace wider than its header slot", () => {
  assert.match(source, /grid w-full min-w-0 gap-2 sm:grid-cols-2/);
  assert.doesNotMatch(source, /min-w-\[18rem\]/);
  assert.doesNotMatch(source, /xl:min-w-\[38rem\]/);
  assert.doesNotMatch(source, /xl:grid-cols-\[minmax\(14rem/);
});
