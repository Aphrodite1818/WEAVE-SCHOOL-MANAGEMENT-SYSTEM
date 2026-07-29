import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  ClipboardCheck,
  Clock3,
  Lock,
  MapPin,
  RefreshCw,
} from "lucide-react";

import DashboardLayout from "../../../components/layout/DashboardLayout";
import EmptyState from "../../../components/shared/EmptyState";
import LoadingState from "../../../components/shared/LoadingState";
import Button from "../../../components/ui/Button";
import Card from "../../../components/ui/Card";
import Input from "../../../components/ui/Input";
import Modal from "../../../components/ui/Modal";
import { classService } from "../../../services/academicsService";
import { getErrorMessage, isAbortError } from "../../../services/api";
import { parentService } from "../../../services/parentService";
import { attendanceService, getBrowserLocation } from "../api/attendanceService";
import GeofenceMapPicker from "./GeofenceMapPicker";

const todayIso = () => new Date().toISOString().slice(0, 10);
const addDays = (isoDate, days) => {
  const date = new Date(`${isoDate}T00:00:00`);
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
};
const titleCase = (value) =>
  String(value || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
const asItems = (response) => (Array.isArray(response?.items) ? response.items : []);
const className = (item) =>
  [item?.name, item?.arm].filter(Boolean).join(" ") || item?.id || "Class";
const studentLabel = (item) =>
  [item?.first_name, item?.last_name].filter(Boolean).join(" ") ||
  item?.student_name ||
  item?.admission_number ||
  item?.id ||
  "Student";
const countRecords = (sheet) =>
  (sheet?.records || []).reduce((totals, record) => {
    totals[record.status] = (totals[record.status] || 0) + 1;
    return totals;
  }, {});

function ErrorBanner({ message }) {
  if (!message) return null;
  return (
    <div className="rounded-lg border border-error/30 bg-error-soft px-4 py-3 text-sm font-semibold text-error">
      {message}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="rounded-lg border border-border/70 bg-surface px-3 py-2">
      <p className="text-xs font-medium text-text-muted">{label}</p>
      <p className="mt-1 text-lg font-semibold text-text">{value}</p>
    </div>
  );
}

function SheetCard({ sheet, onSubmit, onApprove, onLock, actionBusy }) {
  const totals = countRecords(sheet);
  const submitBusy = actionBusy === `submit:${sheet.id}`;
  const approveBusy = actionBusy === `approve:${sheet.id}`;
  const lockBusy = actionBusy === `lock:${sheet.id}`;
  return (
    <Card className="p-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-sm font-semibold text-text">{sheet.attendance_date}</p>
          <p className="text-xs text-text-muted">{titleCase(sheet.status)}</p>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
          <Stat label="Present" value={totals.present || 0} />
          <Stat label="Late" value={totals.late || 0} />
          <Stat label="Absent" value={totals.absent || 0} />
          <Stat label="Excused" value={totals.excused || 0} />
          <Stat label="Unmarked" value={totals.unmarked || 0} />
        </div>
        <div className="flex flex-wrap gap-2">
          {onSubmit ? (
            <Button size="sm" variant="success" onClick={() => onSubmit(sheet.id)} disabled={Boolean(actionBusy)}>
              <CheckCircle2 size={16} />
              {submitBusy ? "Submitting..." : "Submit"}
            </Button>
          ) : null}
          {onApprove ? (
            <Button size="sm" variant="outline" onClick={() => onApprove(sheet.id)} disabled={Boolean(actionBusy)}>
              <ClipboardCheck size={16} />
              {approveBusy ? "Approving..." : "Approve"}
            </Button>
          ) : null}
          {onLock ? (
            <Button size="sm" variant="outline" onClick={() => onLock(sheet.id)} disabled={Boolean(actionBusy)}>
              <Lock size={16} />
              {lockBusy ? "Locking..." : "Lock"}
            </Button>
          ) : null}
        </div>
      </div>
    </Card>
  );
}

function ActionConfirmModal({ action, actionBusy, onCancel, onConfirm }) {
  return (
    <Modal
      open={Boolean(action)}
      title={action?.title || "Confirm action"}
      description={action?.description}
      onClose={onCancel}
      footer={
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onCancel} disabled={Boolean(actionBusy)}>
            Cancel
          </Button>
          <Button
            type="button"
            variant={action?.variant || "primary"}
            onClick={onConfirm}
            disabled={Boolean(actionBusy)}
          >
            {actionBusy ? action?.busyLabel || "Working..." : action?.confirmLabel || "Confirm"}
          </Button>
        </div>
      }
    >
      {action?.body ? <p className="text-sm text-text-muted">{action.body}</p> : null}
    </Modal>
  );
}

function RecordsTable({ records }) {
  if (!records.length) {
    return (
      <Card className="p-5">
        <EmptyState
          icon={ClipboardCheck}
          title="No attendance records"
          description="Records will appear after a class sheet has been opened and marked."
        />
      </Card>
    );
  }
  return (
    <div className="max-h-[560px] overflow-auto overscroll-contain rounded-lg border border-border/70 bg-surface">
      <table className="min-w-[720px] w-full text-left text-sm">
        <thead className="bg-surface-muted text-xs uppercase text-text-muted">
          <tr>
            <th className="px-3 py-2">Date</th>
            <th className="px-3 py-2">Status</th>
            <th className="px-3 py-2">Reason</th>
            <th className="px-3 py-2">Marked</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border/70">
          {records.map((record) => (
            <tr key={record.id}>
              <td className="px-3 py-2">{record.attendance_date || record.created_at?.slice(0, 10) || "-"}</td>
              <td className="px-3 py-2 font-semibold">{titleCase(record.status)}</td>
              <td className="px-3 py-2">{record.reason || record.notes || "-"}</td>
              <td className="px-3 py-2">{record.marked_at ? new Date(record.marked_at).toLocaleString() : "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AdminAttendance({ rangeStart, rangeEnd }) {
  const [sheets, setSheets] = useState([]);
  const [workforce, setWorkforce] = useState([]);
  const [settings, setSettings] = useState(null);
  const [geofences, setGeofences] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionBusy, setActionBusy] = useState("");
  const [pendingAction, setPendingAction] = useState(null);
  const [geofenceForm, setGeofenceForm] = useState({
    name: "",
    latitude: "",
    longitude: "",
    radius_m: "150",
    is_primary: true,
  });

  const load = useCallback(async ({ signal } = {}) => {
    setLoading(true);
    setError("");
    try {
      const [settingsResponse, geofenceResponse, sheetResponse, workforceResponse, analyticsResponse] =
        await Promise.all([
          attendanceService.admin.getSettings({ signal }),
          attendanceService.admin.listGeofences({}, { signal }),
          attendanceService.admin.listSheets({ start_date: rangeStart, end_date: rangeEnd }),
          attendanceService.admin.listWorkforce({ start_date: rangeStart, end_date: rangeEnd }),
          attendanceService.admin.getAnalytics({ start_date: rangeStart, end_date: rangeEnd }),
        ]);
      setSettings(settingsResponse);
      setGeofences(asItems(geofenceResponse));
      setSheets(asItems(sheetResponse));
      setWorkforce(asItems(workforceResponse));
      setAnalytics(analyticsResponse);
    } catch (err) {
      if (!isAbortError(err)) setError(getErrorMessage(err, "Could not load attendance."));
    } finally {
      setLoading(false);
    }
  }, [rangeEnd, rangeStart]);

  useEffect(() => {
    const controller = new AbortController();
    load({ signal: controller.signal });
    return () => controller.abort();
  }, [load]);

  const createGeofence = async () => {
    setActionBusy("geofence:create");
    setError("");
    try {
      await attendanceService.admin.createGeofence({
        ...geofenceForm,
        radius_m: Number(geofenceForm.radius_m),
      });
      setGeofenceForm({ name: "", latitude: "", longitude: "", radius_m: "150", is_primary: true });
      await load();
    } catch (err) {
      setError(getErrorMessage(err, "Could not save geofence."));
    } finally {
      setActionBusy("");
    }
  };

  const toggleGeofenceRequirement = async () => {
    setActionBusy("settings:geofence");
    setError("");
    try {
      await attendanceService.admin.updateSettings({
        require_geofence_for_workforce: !settings?.require_geofence_for_workforce,
      });
      await load();
    } catch (err) {
      setError(getErrorMessage(err, "Could not update attendance settings."));
    } finally {
      setActionBusy("");
      setPendingAction(null);
    }
  };

  const runSheetAction = async (key, fallback, request) => {
    setActionBusy(key);
    setError("");
    try {
      await request();
      await load();
    } catch (err) {
      setError(getErrorMessage(err, fallback));
    } finally {
      setActionBusy("");
      setPendingAction(null);
    }
  };

  if (loading) return <LoadingState label="Loading attendance operations..." />;

  return (
    <section className="space-y-4">
      <ErrorBanner message={error} />
      <div className="grid gap-3 md:grid-cols-4">
        <Stat label="Student records" value={Object.values(analytics?.student_totals || {}).reduce((a, b) => a + b, 0)} />
        <Stat label="Workforce records" value={workforce.length} />
        <Stat label="Geofences" value={geofences.length} />
        <Stat label="Workforce geofence" value={settings?.require_geofence_for_workforce ? "Required" : "Optional"} />
      </div>
      <Card className="p-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-sm font-semibold text-text">Workforce geofencing</p>
            <p className="text-xs text-text-muted">Server-side location evaluation is evidence only.</p>
          </div>
          <Button
            variant="outline"
            size="sm"
            disabled={Boolean(actionBusy)}
            onClick={() =>
              setPendingAction({
                title: settings?.require_geofence_for_workforce
                  ? "Make workforce geofence optional"
                  : "Require workforce geofence",
                description: "This changes how teacher and staff workforce attendance is evaluated.",
                confirmLabel: settings?.require_geofence_for_workforce ? "Make optional" : "Require geofence",
                busyLabel: "Updating...",
                onConfirm: toggleGeofenceRequirement,
              })
            }
          >
            <MapPin size={16} />
            {actionBusy === "settings:geofence"
              ? "Updating..."
              : settings?.require_geofence_for_workforce
                ? "Make optional"
                : "Require for workforce"}
          </Button>
        </div>
      </Card>
      <Card className="p-4">
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
          <GeofenceMapPicker
            latitude={geofenceForm.latitude}
            longitude={geofenceForm.longitude}
            radiusM={geofenceForm.radius_m}
            onChange={(point) =>
              setGeofenceForm((current) => ({
                ...current,
                latitude: point.latitude.toFixed(6),
                longitude: point.longitude.toFixed(6),
              }))
            }
          />
          <div className="space-y-3">
            <Input label="Geofence name" value={geofenceForm.name} onChange={(event) => setGeofenceForm((current) => ({ ...current, name: event.target.value }))} />
            <Input label="Latitude" value={geofenceForm.latitude} onChange={(event) => setGeofenceForm((current) => ({ ...current, latitude: event.target.value }))} />
            <Input label="Longitude" value={geofenceForm.longitude} onChange={(event) => setGeofenceForm((current) => ({ ...current, longitude: event.target.value }))} />
            <Input label="Radius m" type="number" value={geofenceForm.radius_m} onChange={(event) => setGeofenceForm((current) => ({ ...current, radius_m: event.target.value }))} />
            <Button className="w-full" onClick={createGeofence} disabled={Boolean(actionBusy)}>
              <MapPin size={16} />
              {actionBusy === "geofence:create" ? "Saving..." : "Save geofence"}
            </Button>
          </div>
        </div>
      </Card>
      <div className="max-h-[560px] space-y-3 overflow-y-auto overscroll-contain pr-1">
        {sheets.length ? sheets.map((sheet) => (
          <SheetCard
            key={sheet.id}
            sheet={sheet}
            actionBusy={actionBusy}
            onApprove={(id) =>
              setPendingAction({
                title: "Approve attendance sheet",
                description: "Approved sheets move forward for administrative control.",
                confirmLabel: "Approve sheet",
                busyLabel: "Approving...",
                onConfirm: () =>
                  runSheetAction(`approve:${id}`, "Could not approve sheet.", () =>
                    attendanceService.admin.approveSheet(id),
                  ),
              })
            }
            onLock={(id) =>
              setPendingAction({
                title: "Lock attendance sheet",
                description: "Locked attendance sheets should be treated as final records.",
                confirmLabel: "Lock sheet",
                busyLabel: "Locking...",
                variant: "danger",
                onConfirm: () =>
                  runSheetAction(`lock:${id}`, "Could not lock sheet.", () =>
                    attendanceService.admin.lockSheet(id),
                  ),
              })
            }
          />
        )) : (
          <Card className="p-5"><EmptyState icon={ClipboardCheck} title="No student sheets" description="No class attendance sheets exist for this range." /></Card>
        )}
      </div>
      <ActionConfirmModal
        action={pendingAction}
        actionBusy={actionBusy}
        onCancel={() => setPendingAction(null)}
        onConfirm={() => pendingAction?.onConfirm?.()}
      />
    </section>
  );
}

function TeacherAttendance({ rangeStart, rangeEnd }) {
  const [classes, setClasses] = useState([]);
  const [classId, setClassId] = useState("");
  const [sheets, setSheets] = useState([]);
  const [workforce, setWorkforce] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [pendingAction, setPendingAction] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [classResponse, sheetResponse, workforceResponse] = await Promise.all([
        classService.getClasses({ limit: 100, active_only: true }),
        attendanceService.teacher.listSheets({ start_date: rangeStart, end_date: rangeEnd }),
        attendanceService.teacher.myWorkforce({ start_date: rangeStart, end_date: rangeEnd }),
      ]);
      const classItems = asItems(classResponse);
      setClasses(classItems);
      setClassId((current) => current || classItems[0]?.id || "");
      setSheets(asItems(sheetResponse));
      setWorkforce(asItems(workforceResponse));
    } catch (err) {
      setError(getErrorMessage(err, "Could not load teacher attendance."));
    } finally {
      setLoading(false);
    }
  }, [rangeEnd, rangeStart]);

  useEffect(() => {
    load();
  }, [load]);

  const openSheet = async () => {
    if (!classId) return;
    setBusy("open");
    setError("");
    try {
      await attendanceService.teacher.openSheet({ class_id: classId, attendance_date: todayIso() });
      await load();
    } catch (err) {
      setError(getErrorMessage(err, "Could not open attendance sheet."));
    } finally {
      setBusy("");
    }
  };

  const workforceAction = async (action) => {
    setBusy(`workforce:${action}`);
    setError("");
    try {
      const location = await getBrowserLocation();
      if (action === "in") await attendanceService.teacher.checkIn({ location });
      else await attendanceService.teacher.checkOut({ location });
      await load();
    } catch (err) {
      setError(getErrorMessage(err, err.message || "Could not complete attendance action."));
    } finally {
      setBusy("");
    }
  };

  const submitSheet = async (id) => {
    setBusy(`submit:${id}`);
    setError("");
    try {
      await attendanceService.teacher.submitSheet(id);
      await load();
    } catch (err) {
      setError(getErrorMessage(err, "Could not submit sheet."));
    } finally {
      setBusy("");
      setPendingAction(null);
    }
  };

  if (loading) return <LoadingState label="Loading teacher attendance..." />;

  return (
    <section className="space-y-4">
      <ErrorBanner message={error} />
      <Card className="p-4">
        <div className="grid gap-3 md:grid-cols-[1fr_auto_auto_auto] md:items-end">
          <label className="text-sm font-medium text-text-soft">
            Class
            <select className="input-base mt-1.5" value={classId} onChange={(event) => setClassId(event.target.value)}>
              {classes.map((item) => <option key={item.id} value={item.id}>{className(item)}</option>)}
            </select>
          </label>
          <Button onClick={openSheet} disabled={Boolean(busy) || !classId}>
            <ClipboardCheck size={16} />
            {busy === "open" ? "Opening..." : "Open today"}
          </Button>
          <Button variant="success" onClick={() => workforceAction("in")} disabled={Boolean(busy)}>
            <MapPin size={16} />
            {busy === "workforce:in" ? "Checking in..." : "Check in"}
          </Button>
          <Button variant="outline" onClick={() => workforceAction("out")} disabled={Boolean(busy)}>
            <Clock3 size={16} />
            {busy === "workforce:out" ? "Checking out..." : "Check out"}
          </Button>
        </div>
      </Card>
      <div className="grid gap-3 md:grid-cols-3">
        <Stat label="Sheets" value={sheets.length} />
        <Stat label="Workforce days" value={workforce.length} />
        <Stat label="Today" value={todayIso()} />
      </div>
      <div className="max-h-[560px] space-y-3 overflow-y-auto overscroll-contain pr-1">
        {sheets.length ? sheets.map((sheet) => (
          <SheetCard
            key={sheet.id}
            sheet={sheet}
            actionBusy={busy}
            onSubmit={(id) =>
              setPendingAction({
                title: "Submit attendance sheet",
                description: "Submitted sheets are sent forward for admin review.",
                confirmLabel: "Submit sheet",
                busyLabel: "Submitting...",
                onConfirm: () => submitSheet(id),
              })
            }
          />
        )) : (
          <Card className="p-5"><EmptyState icon={ClipboardCheck} title="No sheets" description="Open a class sheet to begin marking attendance." /></Card>
        )}
      </div>
      <ActionConfirmModal
        action={pendingAction}
        actionBusy={busy}
        onCancel={() => setPendingAction(null)}
        onConfirm={() => pendingAction?.onConfirm?.()}
      />
    </section>
  );
}

function StudentAttendance({ rangeStart, rangeEnd }) {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    attendanceService.student.myRecords({ start_date: rangeStart, end_date: rangeEnd })
      .then((response) => setRecords(asItems(response)))
      .catch((err) => setError(getErrorMessage(err, "Could not load attendance history.")))
      .finally(() => setLoading(false));
  }, [rangeEnd, rangeStart]);

  if (loading) return <LoadingState label="Loading attendance history..." />;
  return <section className="space-y-4"><ErrorBanner message={error} /><RecordsTable records={records} /></section>;
}

function ParentAttendance({ rangeStart, rangeEnd }) {
  const [children, setChildren] = useState([]);
  const [childId, setChildId] = useState("");
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    parentService.getMyStudents()
      .then((response) => {
        const items = asItems(response);
        setChildren(items);
        setChildId((current) => current || items[0]?.student_id || items[0]?.id || "");
      })
      .catch((err) => setError(getErrorMessage(err, "Could not load linked students.")))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!childId) return;
    attendanceService.parent.studentRecords(childId, { start_date: rangeStart, end_date: rangeEnd })
      .then((response) => setRecords(asItems(response)))
      .catch((err) => setError(getErrorMessage(err, "Could not load student attendance.")));
  }, [childId, rangeEnd, rangeStart]);

  if (loading) return <LoadingState label="Loading family attendance..." />;
  return (
    <section className="space-y-4">
      <ErrorBanner message={error} />
      <Card className="p-4">
        <label className="text-sm font-medium text-text-soft">
          Student
          <select className="input-base mt-1.5" value={childId} onChange={(event) => setChildId(event.target.value)}>
            {children.map((child) => (
              <option key={child.student_id || child.id} value={child.student_id || child.id}>
                {studentLabel(child)}
              </option>
            ))}
          </select>
        </label>
      </Card>
      <RecordsTable records={records} />
    </section>
  );
}

const copyByRole = {
  admin: {
    title: "Attendance",
    description: "Review student sheets, manage workforce attendance settings, and maintain geofences.",
  },
  teacher: {
    title: "Attendance",
    description: "Open class sheets and record your workforce check-in and check-out.",
  },
  student: {
    title: "Attendance",
    description: "Review your attendance history.",
  },
  parent: {
    title: "Attendance",
    description: "Review attendance history for linked students.",
  },
};

function AttendanceWorkspace({ role }) {
  const [rangeStart, setRangeStart] = useState(addDays(todayIso(), -14));
  const [rangeEnd, setRangeEnd] = useState(todayIso());
  const copy = copyByRole[role] || copyByRole.student;
  const content = useMemo(() => {
    if (role === "admin") return <AdminAttendance rangeStart={rangeStart} rangeEnd={rangeEnd} />;
    if (role === "teacher") return <TeacherAttendance rangeStart={rangeStart} rangeEnd={rangeEnd} />;
    if (role === "parent") return <ParentAttendance rangeStart={rangeStart} rangeEnd={rangeEnd} />;
    return <StudentAttendance rangeStart={rangeStart} rangeEnd={rangeEnd} />;
  }, [rangeEnd, rangeStart, role]);

  return (
    <DashboardLayout role={role} title={copy.title} description={copy.description}>
      <div className="space-y-4">
        <Card className="p-4">
          <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto] md:items-end">
            <Input label="Start" type="date" value={rangeStart} onChange={(event) => setRangeStart(event.target.value)} />
            <Input label="End" type="date" value={rangeEnd} onChange={(event) => setRangeEnd(event.target.value)} />
            <Button variant="outline" onClick={() => { setRangeStart(addDays(todayIso(), -14)); setRangeEnd(todayIso()); }}>
              <RefreshCw size={16} />
              Reset
            </Button>
          </div>
        </Card>
        {content}
      </div>
    </DashboardLayout>
  );
}

export default AttendanceWorkspace;
