import assert from "node:assert/strict";
import test from "node:test";

import { isAssignableClassTeacher } from "./classTeacherEligibility.js";

test("read-only teachers are not offered for class teacher assignment", () => {
  assert.equal(
    isAssignableClassTeacher({
      status: "read_only",
      teacher_account: {
        account_status: "active",
        is_active: true,
      },
    }),
    false,
  );
});

test("only fully active teacher memberships are offered for class teacher assignment", () => {
  assert.equal(
    isAssignableClassTeacher({
      status: "active",
      teacher_account: {
        account_status: "active",
        is_active: true,
      },
    }),
    true,
  );
  assert.equal(
    isAssignableClassTeacher({
      status: "active",
      teacher_account: {
        account_status: "inactive",
        is_active: true,
      },
    }),
    false,
  );
  assert.equal(
    isAssignableClassTeacher({
      status: "active",
      teacher_account: {
        account_status: "active",
        is_active: false,
      },
    }),
    false,
  );
});
