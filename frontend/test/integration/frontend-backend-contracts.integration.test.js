import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  normalizeContractPath,
  verifyFrontendBackendContracts,
} from "../../scripts/verifyFrontendBackendContracts.mjs";

const repoRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "..",
  "..",
);

test("contract-path normalization treats frontend templates and FastAPI parameters equally", () => {
  assert.equal(
    normalizeContractPath("/api/v1/students/${studentId}?include=class"),
    "/students/{}",
  );
  assert.equal(normalizeContractPath("/students/{student_id}"), "/students/{}");
  assert.equal(normalizeContractPath("students/me/"), "/students/me");
});

test("every literal frontend API call has a matching FastAPI method and route", async () => {
  const result = await verifyFrontendBackendContracts(repoRoot);

  assert.ok(result.frontendContracts.size > 25, "expected broad frontend API coverage");
  assert.ok(result.backendContracts.size > 50, "expected broad FastAPI route coverage");
  assert.deepEqual(
    result.missing,
    [],
    result.missing
      .map(
        (contract) =>
          `${contract.key}\n  ${[...new Set(contract.sources)].join("\n  ")}`,
      )
      .join("\n"),
  );
});
