import assert from "node:assert/strict";
import test from "node:test";

import {
  BULK_IMPORT_HISTORY_PAGE_SIZE,
  HISTORY_NEXT_LABEL,
  getActualParentInvitationsQueued,
  getExpectedParentInvitationCount,
  getNextHistoryRequest,
  getStatusChangeHistoryRequest,
  loadImportHistoryPage,
} from "./bulkImportPageLogic.js";

test("uses expected parent invitation count only from dry-run metadata", () => {
  const job = {
    metadata_json: {
      new_parent_invitations_expected: 3,
      result_rows: [
        { parent_invitations_queued: 1 },
        { parent_invitations_queued: 1 },
      ],
    },
  };

  assert.equal(getExpectedParentInvitationCount(job), 3);
});

test("calculates actual queued parent invitations from completed result rows", () => {
  const job = {
    metadata_json: {
      new_parent_invitations_expected: 5,
      result_rows: [
        { status: "created", parent_invitations_queued: 2 },
        { status: "failed", parent_invitations_queued: 0 },
        { status: "created", parent_invitations_queued: 1 },
      ],
    },
  };

  assert.equal(getActualParentInvitationsQueued(job), 3);
});

test("history status change issues one explicit request", async () => {
  const calls = [];
  const request = getStatusChangeHistoryRequest("failed");

  await loadImportHistoryPage({
    listJobs: async (params) => {
      calls.push(params);
      return { items: [], total: 0 };
    },
    skip: request.skip,
    status: request.status,
    setJobs: () => {},
    setJobsTotal: () => {},
    setHistorySkip: () => {},
    setHistoryLoading: () => {},
  });

  assert.deepEqual(calls, [{ skip: 0, limit: BULK_IMPORT_HISTORY_PAGE_SIZE, status: "failed" }]);
});

test("history pagination issues one explicit next-page request", async () => {
  const calls = [];
  const request = getNextHistoryRequest(20, "completed");

  await loadImportHistoryPage({
    listJobs: async (params) => {
      calls.push(params);
      return { items: [{ id: "job-1" }], total: 30 };
    },
    skip: request.skip,
    status: request.status,
    setJobs: () => {},
    setJobsTotal: () => {},
    setHistorySkip: () => {},
    setHistoryLoading: () => {},
  });

  assert.deepEqual(calls, [{ skip: 40, limit: BULK_IMPORT_HISTORY_PAGE_SIZE, status: "completed" }]);
});

test("standard history pagination uses next wording", () => {
  assert.equal(HISTORY_NEXT_LABEL, "Next");
});
