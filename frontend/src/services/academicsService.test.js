import assert from "node:assert/strict";
import test from "node:test";

import { filterClasses } from "./classSearch.js";

const classes = [
  { id: "1", academic_level_name: "JSS 1", arm: "A" },
  { id: "2", academic_level_name: "JSS 1", arm: "B" },
  { id: "3", academic_level_name: "Primary 2", arm: "A" },
  { id: "4", academic_level_name: "Senior Secondary School 3", arm: "Science" },
];

test("single-letter arm searches are consistent", () => {
  assert.deepEqual(
    filterClasses(classes, "A").map((item) => item.id),
    ["1", "3"],
  );
  assert.deepEqual(
    filterClasses(classes, "B").map((item) => item.id),
    ["2"],
  );
});

test("class search handles compact and similar queries", () => {
  assert.deepEqual(
    filterClasses(classes, "jss1a").map((item) => item.id),
    ["1"],
  );
  assert.deepEqual(
    filterClasses(classes, "snrsecsch3").map((item) => item.id),
    ["4"],
  );
});
