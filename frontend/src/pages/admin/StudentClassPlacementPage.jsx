import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, CheckCircle2, Search, Users } from "lucide-react";
import { useNavigate } from "react-router-dom";

import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Input from "../../components/ui/Input";
import SearchableSelect from "../../components/ui/SearchableSelect";
import { useToast } from "../../hooks/useToast";
import academicService from "../../services/academicService";
import {
  academicLevelService,
  classService,
} from "../../services/academicsService";
import { parseApiError } from "../../services/api";
import { studentService } from "../../services/studentService";
import { displayName } from "../../utils/user";

const asItems = (response) =>
  Array.isArray(response)
    ? response
    : Array.isArray(response?.items)
      ? response.items
      : [];

const classLabel = (item) =>
  item?.display_name ||
  [item?.academic_level_name, item?.arm_label].filter(Boolean).join(" ") ||
  item?.id ||
  "Class";

function SelectField({ label, value, options, onChange, placeholder, disabled }) {
  return (
    <SearchableSelect
      label={label}
      value={value || ""}
      options={options}
      placeholder={placeholder || "Select"}
      clearable
      disabled={disabled}
      onChange={onChange}
    />
  );
}

function StudentClassPlacementPage() {
  const navigate = useNavigate();
  const { showSuccess, showError } = useToast();
  const [sessions, setSessions] = useState([]);
  const [levels, setLevels] = useState([]);
  const [classes, setClasses] = useState([]);
  const [students, setStudents] = useState([]);
  const [sessionId, setSessionId] = useState("");
  const [levelId, setLevelId] = useState("");
  const [targetClassId, setTargetClassId] = useState("");
  const [search, setSearch] = useState("");
  const [selectedIds, setSelectedIds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [placing, setPlacing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([
      academicService.listSessions({ limit: 100 }),
      academicLevelService.getLevels({ activeOnly: true }),
      classService.getClasses({ limit: 100 }),
    ])
      .then(([sessionResult, levelResult, classResult]) => {
        if (!active) return;
        const allSessions = asItems(sessionResult);
        const placementSessions = allSessions.filter(
          (item) => item.is_current && String(item.status || "").toLowerCase() === "open",
        );
        setSessions(placementSessions);
        setLevels(asItems(levelResult));
        setClasses(asItems(classResult));
        setSessionId(placementSessions[0]?.id || "");
      })
      .catch((requestError) => {
        if (!active) return;
        setError(parseApiError(requestError, "Failed to load placement options.").message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    setSelectedIds([]);
    setTargetClassId("");
    if (!sessionId || !levelId) {
      setStudents([]);
      return;
    }
    let active = true;
    setLoading(true);
    studentService
      .getAdminStudents({
        academicLevelId: levelId,
        unassignedClass: true,
        status: "active",
        search: search.trim() || undefined,
        limit: 100,
      })
      .then((response) => {
        if (active) setStudents(asItems(response).filter((student) => !student.class_id));
      })
      .catch((requestError) => {
        if (active) {
          setError(parseApiError(requestError, "Failed to load unassigned students.").message);
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [levelId, search, sessionId]);

  const levelOptions = useMemo(
    () => levels.map((item) => ({ value: item.id, label: item.name })),
    [levels],
  );
  const sessionOptions = useMemo(
    () => sessions.map((item) => ({ value: item.id, label: item.name || item.id })),
    [sessions],
  );
  const classOptions = useMemo(
    () =>
      classes
        .filter((item) => item.academic_level_id === levelId && item.is_active !== false)
        .map((item) => ({ value: item.id, label: classLabel(item) })),
    [classes, levelId],
  );
  const allSelected =
    students.length > 0 && students.every((item) => selectedIds.includes(item.id));

  const toggleStudent = (studentId, checked) => {
    setSelectedIds((current) =>
      checked
        ? [...new Set([...current, studentId])]
        : current.filter((id) => id !== studentId),
    );
  };

  const placeStudents = async () => {
    if (!sessionId || !levelId || !targetClassId || selectedIds.length === 0) return;
    setPlacing(true);
    try {
      const result = await studentService.placeStudents({
        academic_session_id: sessionId,
        academic_level_id: levelId,
        target_class_id: targetClassId,
        student_ids: selectedIds,
      });
      showSuccess(`${result.placed_count ?? selectedIds.length} students placed successfully.`);
      setStudents((current) =>
        current.filter((student) => !selectedIds.includes(student.id)),
      );
      setSelectedIds([]);
    } catch (requestError) {
      showError(parseApiError(requestError, "Failed to place selected students.").message);
    } finally {
      setPlacing(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Button
            type="button"
            size="small"
            variant="ghost"
            onClick={() => navigate("/admin/students")}
          >
            <ArrowLeft className="h-4 w-4" /> Student directory
          </Button>
          <h1 className="mt-3 text-xl font-semibold tracking-tight text-text sm:text-[1.65rem]">
            Class Placement
          </h1>
          <p className="mt-1 text-sm text-text-muted">
            Place students who already have a level enrollment but do not yet have a class. Placement is available throughout the current open academic session.
          </p>
        </div>
        <div className="rounded-xl border border-border bg-surface px-4 py-3 text-sm text-text-muted">
          <span className="font-semibold text-text">{selectedIds.length}</span> selected
        </div>
      </div>

      {error ? (
        <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm text-error">
          {error}
        </div>
      ) : null}

      <Card className="p-4 sm:p-5">
        {sessions.length === 0 && !loading ? (
          <div className="mb-4 rounded-xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm text-amber-800">
            Class Placement requires the current academic session to be OPEN.
          </div>
        ) : null}
        <div className="grid gap-4 lg:grid-cols-4">
          <SelectField
            label="Academic session"
            value={sessionId}
            options={sessionOptions}
            onChange={setSessionId}
            placeholder="No open current session"
            disabled={sessions.length <= 1}
          />
          <SelectField
            label="Academic level"
            value={levelId}
            options={levelOptions}
            onChange={setLevelId}
            placeholder="Choose level"
            disabled={!sessionId}
          />
          <SelectField
            label="Target class"
            value={targetClassId}
            options={classOptions}
            onChange={setTargetClassId}
            placeholder={levelId ? "Choose class" : "Choose a level first"}
            disabled={!sessionId || !levelId}
          />
          <Input
            label="Search unassigned students"
            value={search}
            placeholder="Name or admission number"
            onChange={(event) => setSearch(event.target.value)}
            icon={Search}
            disabled={!sessionId || !levelId}
          />
        </div>
      </Card>

      <Card className="overflow-hidden">
        <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3 sm:px-5">
          <div className="flex items-center gap-2">
            <Users className="h-4 w-4 text-primary" />
            <div>
              <p className="font-semibold text-text">Unassigned students</p>
              <p className="text-xs text-text-muted">
                Only students in the selected academic level with no class are shown.
              </p>
            </div>
          </div>
          <Button
            type="button"
            disabled={!sessionId || !targetClassId || selectedIds.length === 0 || placing}
            onClick={placeStudents}
          >
            <CheckCircle2 className="h-4 w-4" />
            {placing ? "Placing..." : `Place ${selectedIds.length || ""} students`.trim()}
          </Button>
        </div>

        {loading ? (
          <div className="p-6"><LoadingState label="Loading placement roster..." /></div>
        ) : !sessionId ? (
          <div className="p-6">
            <EmptyState
              title="No open current session"
              description="Open the current academic session before placing students into classes."
            />
          </div>
        ) : !levelId ? (
          <div className="p-6">
            <EmptyState
              title="Choose an academic level"
              description="The unassigned roster appears after you select a level."
            />
          </div>
        ) : students.length === 0 ? (
          <div className="p-6">
            <EmptyState
              title="No unassigned students"
              description="Every matching student currently has a class placement."
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead className="bg-surface-muted/40 text-left text-xs uppercase tracking-wide text-text-muted">
                <tr>
                  <th className="w-12 px-4 py-3">
                    <input
                      type="checkbox"
                      aria-label="Select all unassigned students"
                      checked={allSelected}
                      onChange={(event) =>
                        setSelectedIds(
                          event.target.checked ? students.map((item) => item.id) : [],
                        )
                      }
                    />
                  </th>
                  <th className="px-4 py-3">Student</th>
                  <th className="px-4 py-3">Admission number</th>
                  <th className="px-4 py-3">Academic level</th>
                  <th className="px-4 py-3">Current class</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {students.map((student) => (
                  <tr key={student.id}>
                    <td className="px-4 py-3">
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(student.id)}
                        aria-label={`Select ${displayName(student)}`}
                        onChange={(event) =>
                          toggleStudent(student.id, event.target.checked)
                        }
                      />
                    </td>
                    <td className="px-4 py-3 font-semibold text-text">
                      {displayName(student)}
                    </td>
                    <td className="px-4 py-3 text-text-muted">
                      {student.admission_number || "—"}
                    </td>
                    <td className="px-4 py-3 text-text-muted">
                      {student.academic_level_name ||
                        levelOptions.find((item) => item.value === levelId)?.label ||
                        "—"}
                    </td>
                    <td className="px-4 py-3 text-text-muted">Unassigned</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

export default StudentClassPlacementPage;
