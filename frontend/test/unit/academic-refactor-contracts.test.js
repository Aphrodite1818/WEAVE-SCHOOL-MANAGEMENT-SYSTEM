import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = async (path) => readFile(new URL(`../../${path}`, import.meta.url), "utf8");

test("student dashboard keeps Promise.all responses aligned", async () => {
  const source = await read("src/pages/student/StudentDashboardPage.jsx");
  const bundleStart = source.indexOf("const bundle = await getCachedDashboardBundle");
  const bundleEnd = source.indexOf("if (!mounted || controller.signal.aborted) return;", bundleStart);
  const bundle = source.slice(bundleStart, bundleEnd);

  assert.equal((bundle.match(/studentService\.getMyStudent/g) || []).length, 0);
  assert.equal((bundle.match(/studentService\.getMyParentLinks/g) || []).length, 1);
  assert.equal((bundle.match(/studentService\.getMyParentLinkRequests/g) || []).length, 1);
  assert.equal((bundle.match(/dashboardService\.getStudentAnalytics/g) || []).length, 1);
  assert.equal((bundle.match(/academicService\.listMyResults/g) || []).length, 1);
  assert.equal((bundle.match(/reportCardService\.listMyReportCards/g) || []).length, 1);
  assert.equal((bundle.match(/academicService\.listMySubjectCards/g) || []).length, 1);
});

test("term checkout resolves only an unambiguous eligible term", async () => {
  const source = await read("src/services/subscriptionService.js");
  assert.doesNotMatch(source, /TERM_ORDER/);
  assert.match(source, /draftTerms\.length === 1/);
  assert.match(source, /Select the academic term you want to purchase/);
  assert.match(source, /item\.is_current && item\.status === "open"/);
  assert.doesNotMatch(source, /\["open", "closing"\]/);
});

test("teacher assignment class selector uses the backend 500-class contract", async () => {
  const source = await read("src/features/academic-admin/TeacherAssignmentsWorkspace.jsx");
  assert.match(source, /getClasses\(\{ limit: 500, activeOnly: true \}\)/);
});
