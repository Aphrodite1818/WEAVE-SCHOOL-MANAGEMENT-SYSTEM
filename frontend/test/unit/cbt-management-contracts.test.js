import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  buildResultLedgerQuery,
  ResultLedgerFilterError,
  summarizeResultBatches,
} from "../../src/features/cbt/resultLedger.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(__dirname, "../..");
const readSource = (relativePath) => readFile(path.join(frontendRoot, relativePath), "utf8");

test("CBT waiting flow confirms the exact setup challenge", async () => {
  const source = await readSource("src/services/cbtService.js");

  assert.match(source, /\/cbt\/pairing\/status/);
  assert.match(source, /status\.server_id/);
  assert.match(source, /status\?\.status === "expired"/);
  assert.match(source, /status\?\.status === "invalidated"/);
  assert.doesNotMatch(source, /existingServerIds/);
});

test("CBT management is protected by the current subscription feature guard", async () => {
  const provider = await readSource("src/features/subscriptions/SubscriptionProvider.jsx");
  const nav = await readSource("src/components/layout/navConfig.js");

  assert.doesNotMatch(provider, /MANAGEMENT_VISIBLE_FEATURES/);
  assert.match(nav, /label: "CBT Servers"[\s\S]*featureCode: FEATURE_CODES\.CBT_PAIRING/);
});

test("CBT result ledger query maps role scope, pagination, and filters to the backend contract", () => {
  const examId = "a4e5d117-e361-46be-9b0b-55ee9c18b889";
  const sessionId = "df201393-e867-4e2d-a0b4-032e66b5afbc";
  const termId = "c4086ff3-97c9-4bc9-b269-acac2d63c25e";
  const levelId = "e48ac3aa-37cb-4c0e-8dfc-2e71e77def87";
  const subjectId = "10e0677e-ae26-4ed0-a8a1-e2c3695f37ec";
  const componentId = "4b05a4fc-7e31-4bd3-873f-3d0edbe96114";
  const adminQuery = buildResultLedgerQuery({
    role: "admin",
    page: 3,
    pageSize: 25,
    filters: {
      status: "completed_with_rejections",
      serverId: "50b7eec5-4d7a-4d52-8fa5-e0f945cd6ef1",
      sourceExamId: examId,
      academicSessionId: sessionId,
      academicTermId: termId,
      academicLevelId: levelId,
      curriculumSubjectId: subjectId,
      assessmentComponentId: componentId,
      ingestionReference: " CBT-2026-000184 ",
      createdFrom: "2026-09-01",
      createdTo: "2026-09-08",
    },
  });
  assert.equal(adminQuery.skip, 50);
  assert.equal(adminQuery.limit, 25);
  assert.equal(adminQuery.status, "completed_with_rejections");
  assert.equal(adminQuery.cbt_server_id, "50b7eec5-4d7a-4d52-8fa5-e0f945cd6ef1");
  assert.equal(adminQuery.source_exam_id, examId);
  assert.equal(adminQuery.academic_session_id, sessionId);
  assert.equal(adminQuery.academic_term_id, termId);
  assert.equal(adminQuery.academic_level_id, levelId);
  assert.equal(adminQuery.curriculum_subject_id, subjectId);
  assert.equal(adminQuery.assessment_component_id, componentId);
  assert.equal(adminQuery.ingestion_reference, "CBT-2026-000184");
  assert.equal(
    adminQuery.created_from,
    new Date("2026-09-01T00:00:00").toISOString(),
  );
  assert.equal(
    adminQuery.created_to,
    new Date("2026-09-08T23:59:59.999").toISOString(),
  );
  assert.equal("tenant_id" in adminQuery, false);

  const superadminQuery = buildResultLedgerQuery({
    role: "superadmin",
    filters: {
      tenantId: "c07978a8-167d-4420-a04b-0d9854b87bec",
      serverId: "50b7eec5-4d7a-4d52-8fa5-e0f945cd6ef1",
    },
  });
  assert.equal(superadminQuery.tenant_id, "c07978a8-167d-4420-a04b-0d9854b87bec");
  assert.equal(superadminQuery.cbt_server_id, "50b7eec5-4d7a-4d52-8fa5-e0f945cd6ef1");
});

test("CBT result ledger filters reject stale selections and invalid date ranges", () => {
  assert.throws(
    () => buildResultLedgerQuery({ filters: { sourceExamId: "not-a-uuid" } }),
    ResultLedgerFilterError,
  );
  assert.throws(
    () =>
      buildResultLedgerQuery({
        filters: { createdFrom: "2026-09-08", createdTo: "2026-09-01" },
      }),
    /From date cannot be after to date/,
  );
});

test("CBT result ledger summary distinguishes matching totals from visible score counts", () => {
  assert.deepEqual(
    summarizeResultBatches(
      [
        { received_count: 12, applied_count: 10, rejected_count: 2 },
        { received_count: 8, applied_count: 7, rejected_count: 0 },
      ],
      42,
    ),
    { total: 42, received: 20, applied: 17, rejected: 2 },
  );
});

test("admin and superadmin consume every result audit route", async () => {
  const service = await readSource("src/services/cbtResultLedgerService.js");
  const adminRoutes = await readSource("src/routes/adminRoutes.jsx");
  const superadminRoutes = await readSource("src/routes/superadminRoutes.jsx");
  const ledgerPage = await readSource("src/features/cbt/CBTResultLedgerPage.jsx");

  assert.match(service, /tenantAdminBasePath = "\/tenant-admin\/cbt\/result-ingestions"/);
  assert.match(service, /superadminBasePath = "\/superadmin\/cbt\/result-ingestions"/);
  assert.match(service, /getTenantFilterOptions/);
  assert.match(service, /getSuperadminFilterOptions/);
  assert.match(service, /tenantAdminBasePath}\/filter-options/);
  assert.match(service, /superadminBasePath}\/filter-options/);
  assert.doesNotMatch(service, /\/cbt\/results\/audit\/filter-options/);
  assert.match(service, /listTenantBatches/);
  assert.match(service, /getTenantBatch/);
  assert.match(service, /listTenantBatchItems/);
  assert.match(service, /listSuperadminBatches/);
  assert.match(service, /getSuperadminBatch/);
  assert.match(service, /listSuperadminBatchItems/);
  assert.match(adminRoutes, /path="\/admin\/cbt\/results"/);
  assert.match(adminRoutes, /<CBTHistoricalAccessRouteGuard>/);
  assert.match(superadminRoutes, /path="\/superadmin\/cbt-results"/);
  assert.match(ledgerPage, /roleApi\.get\(batchRecordId\)/);
  assert.match(ledgerPage, /roleApi\.listItems\(batchRecordId/);
  assert.match(ledgerPage, /outcome: nextOutcome/);
});

test("CBT audit filters use backend-owned labels while retaining IDs internally", async () => {
  const ledgerPage = await readSource("src/features/cbt/CBTResultLedgerPage.jsx");

  assert.match(ledgerPage, /normalizeFilterOptions\(response\)/);
  assert.match(ledgerPage, /provided\.exams/);
  assert.match(ledgerPage, /provided\.sessions/);
  assert.match(ledgerPage, /provided\.assessment_components/);
  assert.match(ledgerPage, /value=\{filters\.sourceExamId\}/);
  assert.match(ledgerPage, /onChange=\{updateFilter\("sourceExamId"\)\}/);
  assert.match(ledgerPage, /value=\{option\.id\}>\{option\.label\}/);
  assert.match(ledgerPage, /Batch reference[\s\S]*ingestionReference/);
  assert.doesNotMatch(ledgerPage, /batches\.map\([\s\S]*normalizeFilterOptions/);
  assert.doesNotMatch(ledgerPage, /placeholder="[^"]*(Batch ID|Source exam ID)/);
});

test("CBT audit presents human evidence and confines UUIDs to technical details", async () => {
  const ledgerPage = await readSource("src/features/cbt/CBTResultLedgerPage.jsx");

  assert.match(ledgerPage, /source_exam_title/);
  assert.match(ledgerPage, /ingestion_reference/);
  assert.match(ledgerPage, /Exam title unavailable/);
  assert.match(ledgerPage, /Reference unavailable/);
  assert.match(ledgerPage, /<summary[^>]*>\s*Technical details\s*<\/summary>/);
  assert.match(ledgerPage, /SCORE_CONFLICT/);
  assert.match(ledgerPage, /CBT submitted:/);
  assert.match(ledgerPage, /Existing Weave score:/);
  assert.match(ledgerPage, /Weave retained:/);
  assert.match(ledgerPage, /same score already existed/);
  assert.match(ledgerPage, /student_subject_result_id/);
  assert.match(ledgerPage, /resolved_teacher_assignment_id/);
  assert.doesNotMatch(ledgerPage, /overwrite|save score|edit result/i);
});

test("CBT ledger header keeps navigation and refresh actions in one responsive row", async () => {
  const ledgerPage = await readSource("src/features/cbt/CBTResultLedgerPage.jsx");

  assert.match(ledgerPage, /justify-between/);
  assert.match(ledgerPage, /navigate\("\/admin\/cbt"\)/);
  assert.match(ledgerPage, /className="hidden sm:inline">Refresh/);
});

test("CBT ledger keeps its filter controls in a compact collapsible panel", async () => {
  const ledgerPage = await readSource("src/features/cbt/CBTResultLedgerPage.jsx");

  assert.match(ledgerPage, /const \[filtersOpen, setFiltersOpen\] = useState\(false\)/);
  assert.match(ledgerPage, /aria-expanded=\{filtersOpen\}/);
  assert.match(ledgerPage, /aria-controls="cbt-ledger-filters"/);
  assert.match(ledgerPage, /activeFilterCount/);
  assert.match(ledgerPage, /setFiltersOpen\(false\)/);
  assert.match(ledgerPage, /xl:grid-cols-3/);
});

test("downgraded admins retain historical ledger access without pairing controls", async () => {
  const accessHook = await readSource("src/features/cbt/useCbtHistoricalAccess.js");
  const routeGuard = await readSource("src/routes/CBTHistoricalAccessRouteGuard.jsx");
  const serverPage = await readSource("src/pages/admin/CBTServersPage.jsx");
  const nav = await readSource("src/components/layout/navConfig.js");

  assert.match(accessHook, /listTenantBatches\(\{/);
  assert.match(accessHook, /Number\(response\?\.total \|\| 0\) > 0/);
  assert.match(accessHook, /historyState\.tenantKey === tenantKey/);
  assert.match(accessHook, /enabled = true/);
  assert.match(accessHook, /catch\(\(error\) => \(\{ allowed: false, error \}\)\)/);
  assert.match(routeGuard, /useCbtHistoricalAccess/);
  assert.match(routeGuard, /CBT access could not be verified/);
  assert.match(nav, /label: "CBT Servers"[\s\S]*allowHistoricalAccess: true/);
  assert.match(serverPage, /navigate\("\/admin\/cbt\/results"\)/);
  assert.match(serverPage, /!featureGuard\.allowed/);
  assert.match(serverPage, /Historical CBT access is limited on this plan/);
  assert.match(serverPage, /!featureGuard\.allowed \|\|[\s\S]*resourceGuard\.allowed === false/);
});
