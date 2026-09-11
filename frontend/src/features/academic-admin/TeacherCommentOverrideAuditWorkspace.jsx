import { History, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import { useToast } from "../../hooks/useToast";
import { academicService } from "../../services/academicService";
import { getErrorMessage } from "../../services/api";
import { reportCommentService } from "../../services/reportCommentService";
import { studentService } from "../../services/studentService";
import {
  Input,
  SelectControl,
  WorkspacePanel,
} from "./AcademicWorkspacePrimitives";

const asItems = (response) =>
  Array.isArray(response)
    ? response
    : Array.isArray(response?.items)
      ? response.items
      : [];

const studentLabel = (student) => {
  const name = [student.first_name, student.last_name].filter(Boolean).join(" ") || "Student";
  return student.admission_number ? `${name} · ${student.admission_number}` : name;
};

const termLabel = (term) =>
  String(term?.display_name || term?.name || "Term").replaceAll("_", " ");

const formatDateTime = (value) => {
  if (!value) return "Not recorded";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
};

export default function TeacherCommentOverrideAuditWorkspace({ onContextChange }) {
  const { showError } = useToast();
  const [sessions, setSessions] = useState([]);
  const [terms, setTerms] = useState([]);
  const [students, setStudents] = useState([]);
  const [filters, setFilters] = useState({
    student_id: "",
    academic_session_id: "",
    academic_term_id: "",
  });
  const [search, setSearch] = useState("");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingHistory, setLoadingHistory] = useState(false);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      setLoading(true);
      try {
        const [sessionResponse, termResponse, studentResponse] = await Promise.all([
          academicService.listSessions({ limit: 100 }),
          academicService.listTerms({ limit: 100 }),
          studentService.getAdminStudents({ limit: 100, includeArchived: true }),
        ]);
        if (!mounted) return;
        const nextSessions = asItems(sessionResponse);
        const nextTerms = asItems(termResponse);
        const nextStudents = asItems(studentResponse);
        const currentSession = nextSessions.find((item) => item.is_current) || nextSessions[0] || null;
        const currentTerm =
          nextTerms.find(
            (item) =>
              item.is_current &&
              (!currentSession || item.academic_session_id === currentSession.id),
          ) ||
          nextTerms.find(
            (item) => !currentSession || item.academic_session_id === currentSession.id,
          ) ||
          null;

        setSessions(nextSessions);
        setTerms(nextTerms);
        setStudents(nextStudents);
        setFilters((current) => ({
          ...current,
          academic_session_id: current.academic_session_id || currentSession?.id || "",
          academic_term_id: current.academic_term_id || currentTerm?.id || "",
        }));
        onContextChange?.({ currentSession, currentTerm });
      } catch (error) {
        showError(getErrorMessage(error, "Could not load override audit filters."));
      } finally {
        if (mounted) setLoading(false);
      }
    };
    load();
    return () => {
      mounted = false;
    };
  }, [onContextChange, showError]);

  const termOptions = useMemo(
    () =>
      terms
        .filter(
          (term) =>
            !filters.academic_session_id ||
            term.academic_session_id === filters.academic_session_id,
        )
        .map((term) => ({ value: term.id, label: termLabel(term) })),
    [filters.academic_session_id, terms],
  );

  const studentOptions = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    return students
      .filter((student) =>
        normalized ? studentLabel(student).toLowerCase().includes(normalized) : true,
      )
      .map((student) => ({
        value: student.id,
        label: studentLabel(student),
        description: [student.academic_level_name, student.class_name, student.class_arm]
          .filter(Boolean)
          .join(" · "),
      }));
  }, [search, students]);

  const loadHistory = useCallback(async () => {
    if (!filters.student_id || !filters.academic_session_id || !filters.academic_term_id) {
      setItems([]);
      return;
    }
    setLoadingHistory(true);
    try {
      const response = await reportCommentService.listTeacherCommentOverrides(filters);
      setItems(asItems(response));
    } catch (error) {
      setItems([]);
      showError(getErrorMessage(error, "Could not load teacher comment override history."));
    } finally {
      setLoadingHistory(false);
    }
  }, [filters, showError]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  return (
    <div className="space-y-4">
      <WorkspacePanel
        title="Teacher comment override audit"
        description="Review append-only administrator overrides for one student and academic period. Historical entries are never edited or deleted from this workspace."
      >
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <SelectControl
            label="Academic session"
            value={filters.academic_session_id}
            options={sessions.map((session) => ({ value: session.id, label: session.name }))}
            onChange={(value) => {
              const nextTerm =
                terms.find((term) => term.academic_session_id === value && term.is_current) ||
                terms.find((term) => term.academic_session_id === value);
              setFilters((current) => ({
                ...current,
                academic_session_id: value,
                academic_term_id: nextTerm?.id || "",
              }));
            }}
            required
          />
          <SelectControl
            label="Academic term"
            value={filters.academic_term_id}
            options={termOptions}
            onChange={(value) =>
              setFilters((current) => ({ ...current, academic_term_id: value }))
            }
            required
          />
          <Input
            label="Find student"
            value={search}
            placeholder="Name or admission number"
            onChange={(event) => setSearch(event.target.value)}
          />
          <SelectControl
            label="Student"
            value={filters.student_id}
            options={studentOptions}
            onChange={(value) =>
              setFilters((current) => ({ ...current, student_id: value }))
            }
            required
          />
        </div>
      </WorkspacePanel>

      <WorkspacePanel
        title="Override history"
        description="Newest entries appear first. Every row preserves the administrator, replacement comment, reason, enrollment/class context, and creation time."
        actions={
          <Button
            type="button"
            size="small"
            variant="outline"
            onClick={loadHistory}
            disabled={loadingHistory || loading}
          >
            <RefreshCw className="h-4 w-4" /> Refresh
          </Button>
        }
      >
        {!filters.student_id ? (
          <div className="rounded-xl border border-dashed border-border px-4 py-10 text-center text-sm text-text-muted">
            Choose a student to inspect teacher-comment overrides.
          </div>
        ) : loadingHistory ? (
          <p className="py-8 text-center text-sm text-text-muted">Loading override history...</p>
        ) : items.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border px-4 py-10 text-center">
            <History className="mx-auto h-6 w-6 text-text-muted" />
            <p className="mt-2 text-sm font-semibold text-text">No overrides recorded</p>
            <p className="mt-1 text-sm text-text-muted">
              The effective comment for this period has not required an administrator override.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {items.map((item, index) => (
              <article key={item.id} className="rounded-xl border border-border/70 bg-surface p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Badge variant="warning">Override #{items.length - index}</Badge>
                    <span className="text-xs text-text-muted">{formatDateTime(item.created_at)}</span>
                  </div>
                  <span className="text-xs font-medium text-text-muted">
                    Admin {String(item.admin_id).slice(0, 8)}
                  </span>
                </div>
                <div className="mt-3 grid gap-3 lg:grid-cols-2">
                  <div className="rounded-lg bg-surface-muted/40 px-3 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Override comment</p>
                    <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-text">{item.comment_text}</p>
                  </div>
                  <div className="rounded-lg bg-surface-muted/40 px-3 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Audit reason</p>
                    <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-text">{item.reason}</p>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </WorkspacePanel>
    </div>
  );
}
