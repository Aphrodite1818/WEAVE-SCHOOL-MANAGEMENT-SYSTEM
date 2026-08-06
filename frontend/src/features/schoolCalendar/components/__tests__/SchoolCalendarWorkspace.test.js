import assert from "node:assert/strict";
import test from "node:test";

import react from "@vitejs/plugin-react";
import { createServer } from "vite";

let vite;
let DayEditor;
let buildDayUpdatePayload;

const createStorage = () => {
  const values = new Map();
  return {
    getItem: (key) => values.get(String(key)) ?? null,
    setItem: (key, value) => values.set(String(key), String(value)),
    removeItem: (key) => values.delete(String(key)),
    clear: () => values.clear(),
  };
};

globalThis.localStorage = createStorage();
globalThis.sessionStorage = createStorage();

const baseForm = () => ({
  day_type: "instructional_day",
  title: "Regular school day",
  description: "",
  school_open: true,
  student_activity_allowed: true,
  student_attendance_required: true,
  workforce_attendance_required: true,
  opens_at: "08:00",
  closes_at: "15:00",
  reason: "Calendar correction",
});

const editorProps = (form, onChange = () => {}) => ({
  day: { calendar_date: "2026-08-06" },
  form,
  busy: false,
  saving: "",
  onChange,
  onClose: () => {},
  onSubmit: () => {},
});

const findElement = (node, predicate) => {
  if (Array.isArray(node)) {
    for (const child of node) {
      const match = findElement(child, predicate);
      if (match) return match;
    }
    return null;
  }

  if (!node || typeof node !== "object" || !node.props) return null;
  if (predicate(node)) return node;
  return findElement(node.props.children, predicate);
};

const textContent = (node) => {
  if (Array.isArray(node)) return node.map(textContent).join(" ");
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (!node || typeof node !== "object" || !node.props) return "";
  return textContent(node.props.children);
};

const hasControl = (tree, label) =>
  Boolean(findElement(tree, (element) => element.props?.label === label));

test.before(async () => {
  vite = await createServer({
    configFile: false,
    plugins: [react()],
    server: { middlewareMode: true },
    appType: "custom",
    logLevel: "silent",
  });

  ({ DayEditor, buildDayUpdatePayload } = await vite.ssrLoadModule(
    "/src/features/schoolCalendar/components/SchoolCalendarWorkspace.jsx",
  ));
});

test.after(async () => {
  await vite?.close();
});

test("selecting Public holiday clears hours, closes operations, and hides incompatible controls", () => {
  let form = baseForm();
  const onChange = (updater) => {
    form = updater(form);
  };

  const openTree = DayEditor(editorProps(form, onChange));
  const dayTypeControl = findElement(
    openTree,
    (element) => element.props?.label === "Day type",
  );

  assert.ok(dayTypeControl, "Day type control should render");
  dayTypeControl.props.onChange("public_holiday");

  assert.deepEqual(
    {
      day_type: form.day_type,
      opens_at: form.opens_at,
      closes_at: form.closes_at,
      school_open: form.school_open,
      student_activity_allowed: form.student_activity_allowed,
      student_attendance_required: form.student_attendance_required,
      workforce_attendance_required: form.workforce_attendance_required,
    },
    {
      day_type: "public_holiday",
      opens_at: "",
      closes_at: "",
      school_open: false,
      student_activity_allowed: false,
      student_attendance_required: false,
      workforce_attendance_required: false,
    },
  );

  const closedTree = DayEditor(editorProps(form, onChange));
  assert.equal(hasControl(closedTree, "Opens at"), false);
  assert.equal(hasControl(closedTree, "Closes at"), false);
  assert.equal(hasControl(closedTree, "School open"), false);
  assert.match(textContent(closedTree), /Operating hours do not apply because the school is closed/);
});

test("Public holiday preset uses the same state transition as the day-type control", () => {
  let form = baseForm();
  const tree = DayEditor(
    editorProps(form, (updater) => {
      form = updater(form);
    }),
  );
  const preset = findElement(
    tree,
    (element) => textContent(element.props?.children) === "Public holiday",
  );

  assert.ok(preset, "Public holiday preset should render");
  preset.props.onClick();

  assert.equal(form.day_type, "public_holiday");
  assert.equal(form.opens_at, "");
  assert.equal(form.closes_at, "");
  assert.equal(form.school_open, false);
  assert.equal(form.student_activity_allowed, false);
  assert.equal(form.student_attendance_required, false);
  assert.equal(form.workforce_attendance_required, false);
});

test("switching back to Instructional day renders operating-hour inputs again", () => {
  let form = {
    ...baseForm(),
    day_type: "public_holiday",
    opens_at: "",
    closes_at: "",
    school_open: false,
    student_activity_allowed: false,
    student_attendance_required: false,
    workforce_attendance_required: false,
  };
  const onChange = (updater) => {
    form = updater(form);
  };

  const closedTree = DayEditor(editorProps(form, onChange));
  const dayTypeControl = findElement(
    closedTree,
    (element) => element.props?.label === "Day type",
  );
  dayTypeControl.props.onChange("instructional_day");

  const reopenedTree = DayEditor(editorProps(form, onChange));
  assert.equal(hasControl(reopenedTree, "Opens at"), true);
  assert.equal(hasControl(reopenedTree, "Closes at"), true);
  assert.equal(hasControl(reopenedTree, "School open"), true);
});

test("closed-day submission payload always contains null hours and false operational flags", () => {
  const payload = buildDayUpdatePayload(
    {
      ...baseForm(),
      day_type: "public_holiday",
      opens_at: "08:00",
      closes_at: "15:00",
      school_open: true,
      student_activity_allowed: true,
      student_attendance_required: true,
      workforce_attendance_required: true,
    },
    "calendar-123",
  );

  assert.equal(payload.calendar_id, "calendar-123");
  assert.equal(payload.opens_at, null);
  assert.equal(payload.closes_at, null);
  assert.equal(payload.school_open, false);
  assert.equal(payload.student_activity_allowed, false);
  assert.equal(payload.student_attendance_required, false);
  assert.equal(payload.workforce_attendance_required, false);
  assert.equal(payload.historical_correction_confirmed, true);
});
