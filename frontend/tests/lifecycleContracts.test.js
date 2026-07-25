import assert from "node:assert/strict";
import test from "node:test";

import {
  buildExplicitNullablePatch,
  getBillingLifecycleLabel,
  normalizeMembershipSummary,
  toLocalDateInput,
} from "../src/utils/lifecycleContracts.js";
import {
  getParentChildId,
  normalizeParentChildRecord,
  readSelectedChildId,
} from "../src/pages/parent/parentPageUtils.js";

test("membership summaries preserve authoritative school metadata", () => {
  assert.deepEqual(
    normalizeMembershipSummary({
      membership_id: "membership-1",
      tenant_id: "tenant-1",
      tenant_name: "Weave Academy",
      tenant_logo_url: "https://example.test/logo.png",
      membership_status: "active",
    }),
    {
      membership_id: "membership-1",
      tenant_id: "tenant-1",
      tenant_name: "Weave Academy",
      tenant_logo_url: "https://example.test/logo.png",
      membership_status: "active",
      joined_at: null,
      ended_at: null,
    },
  );
});

test("membership summaries use stored metadata only as fallback", () => {
  const result = normalizeMembershipSummary(
    { id: "membership-2", tenant_id: "tenant-2", status: "read_only" },
    { tenant_name: "Fallback School", tenant_logo_url: "fallback.png" },
  );
  assert.equal(result.membership_id, "membership-2");
  assert.equal(result.tenant_name, "Fallback School");
  assert.equal(result.membership_status, "read_only");
});

test("billing lifecycle labels do not present expired periods as renewing today", () => {
  assert.equal(getBillingLifecycleLabel(-3, "active"), "Ended 3 days ago");
  assert.equal(getBillingLifecycleLabel(-1, "past_due"), "1 day overdue");
  assert.equal(getBillingLifecycleLabel(0, "cancelled"), "Ends today");
  assert.equal(getBillingLifecycleLabel(5, "active"), "5 days left");
});

test("local date input uses calendar components instead of UTC serialization", () => {
  const date = new Date(2026, 6, 25, 0, 30, 0);
  assert.equal(toLocalDateInput(date), "2026-07-25");
});

test("explicit nullable patches clear optional fields without clearing required values", () => {
  assert.deepEqual(
    buildExplicitNullablePatch(
      { first_name: "Taiwo", state_of_origin: "", arm: "" },
      ["state_of_origin", "arm"],
    ),
    { first_name: "Taiwo", state_of_origin: null, arm: null },
  );
});

test("parent child records retain the link contract", () => {
  const entry = {
    student: { id: "student-1", first_name: "Ada" },
    link: { id: "link-1", relationship_type: "mother" },
  };
  const normalized = normalizeParentChildRecord(entry);
  assert.equal(normalized.student.id, "student-1");
  assert.equal(normalized.link.id, "link-1");
  assert.equal(getParentChildId(entry), "student-1");
  assert.equal(readSelectedChildId([entry]), "student-1");
});
