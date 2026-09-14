import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) =>
  readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("teacher rosters use the shared desktop table and mobile directory rows", async () => {
  const rosterPage = await read("src/pages/teacher/StudentsPage.jsx");

  assert.match(rosterPage, /<DirectoryTable/);
  assert.match(rosterPage, /<MobileDirectoryList label={`\$\{title\} students`}>/);
  assert.match(rosterPage, /<MobilePersonCard key=\{student\.id\}>/);
  assert.doesNotMatch(
    rosterPage,
    /<div className="mobile-scroll-list grid gap-3 md:hidden">/,
  );
});
