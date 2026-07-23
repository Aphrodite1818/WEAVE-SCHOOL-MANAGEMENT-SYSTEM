import { BookOpen, CalendarDays, GraduationCap, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import { useToast } from "../../hooks/useToast";
import { getErrorMessage } from "../../services/api";
import { academicService } from "../../services/academicService";
import { subjectService } from "../../services/subject.service";
import {
  CheckboxControl,
  FormActions,
  Input,
  RecordList,
  SelectControl,
  WorkspaceGrid,
  WorkspacePanel,
} from "./AcademicWorkspacePrimitives";

const BLANK_SESSION = {
  name: "",
  start_date: "",
  end_date: "",
  next_academic_session_id: "",
};
const BLANK_TERM = {
  academic_session_id: "",
  name: "first_term",
  start_date: "",
  end_date: "",
  is_current: false,
  is_active: true,
};
const BLANK_SCALE = {
  grade: "",
  min_score: "",
  max_score: "",
  remark: "",
  is_active: true,
};
const BLANK_SUBJECT = { name: "", code: "", description: "" };

const asItems = (response) =>
  Array.isArray(response)
    ? response
    : Array.isArray(response?.items)
      ? response.items
      : [];

const termLabel = (value) =>
  String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

const dateLabel = (value) =>
  value ? new Date(value).toLocaleDateString() : "Date not set";

function AcademicSetupWorkspace({ activeTab, onContextChange }) {
  const [sessions, setSessions] = useState([]);
  const [terms, setTerms] = useState([]);
  const [scales, setScales] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [sessionForm, setSessionForm] = useState(BLANK_SESSION);
  const [termForm, setTermForm] = useState(BLANK_TERM);
  const [scaleForm, setScaleForm] = useState(BLANK_SCALE);
  const [subjectForm, setSubjectForm] = useState(BLANK_SUBJECT);
  const [editing, setEditing] = useState({ type: "", id: "" });
  const [saving, setSaving] = useState("");
  const [openingSessionId, setOpeningSessionId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const { showSuccess, showError } = useToast();

  const loadWorkspace = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sessionResponse, termResponse, scaleResponse, subjectResponse] =
        await Promise.all([
          academicService.listSessions({ limit: 100 }),
          academicService.listTerms({ limit: 100 }),
          academicService.listGradingScales({ limit: 100 }),
          subjectService.getSubjects({ limit: 100 }),
        ]);
      const nextSessions = asItems(sessionResponse);
      const nextTerms = asItems(termResponse);
      setSessions(nextSessions);
      setTerms(nextTerms);
      setScales(asItems(scaleResponse));
      setSubjects(asItems(subjectResponse));

      const currentSession =
        nextSessions.find((item) => item.is_current) || null;
      const currentTerm = nextTerms.find((item) => item.is_current) || null;
      onContextChange?.({ currentSession, currentTerm });
      setTermForm((current) => ({
        ...current,
        academic_session_id:
          current.academic_session_id || currentSession?.id || nextSessions[0]?.id || "",
      }));
    } catch (err) {
      const message = getErrorMessage(err, "Could not load academic setup.");
      setError(message);
      showError(message);
    } finally {
      setLoading(false);
    }
  }, [onContextChange, showError]);

  useEffect(() => {
    loadWorkspace();
  }, [loadWorkspace]);

  const sessionOptions = useMemo(
    () => sessions.map((item) => ({ value: item.id, label: item.name })),
    [sessions],
  );

  const resetSession = () => {
    setSessionForm(BLANK_SESSION);
    setEditing({ type: "", id: "" });
  };
  const resetTerm = () => {
    setTermForm((current) => ({
      ...BLANK_TERM,
      academic_session_id:
        sessions.find((item) => item.is_current)?.id ||
        current.academic_session_id ||
        sessions[0]?.id ||
        "",
    }));
    setEditing({ type: "", id: "" });
  };
  const resetScale = () => {
    setScaleForm(BLANK_SCALE);
    setEditing({ type: "", id: "" });
  };
  const resetSubject = () => {
    setSubjectForm(BLANK_SUBJECT);
    setEditing({ type: "", id: "" });
  };

  const saveSession = async (event) => {
    event.preventDefault();
    setSaving("session");
    try {
      const payload = {
        name: sessionForm.name,
        start_date: sessionForm.start_date || null,
        end_date: sessionForm.end_date || null,
        next_academic_session_id: sessionForm.next_academic_session_id || null,
      };
      if (editing.type === "session") {
        await academicService.updateSession(editing.id, payload);
      } else {
        await academicService.createSession(payload);
      }
      showSuccess(
        editing.type === "session"
          ? "Academic session updated."
          : "Academic session created.",
      );
      resetSession();
      await loadWorkspace();
    } catch (err) {
      showError(getErrorMessage(err, "Could not save academic session."));
    } finally {
      setSaving("");
    }
  };

  const openSession = async (sessionId) => {
    setOpeningSessionId(sessionId);
    try {
      await academicService.openSession(sessionId);
      showSuccess("Academic session opened.");
      await loadWorkspace();
    } catch (err) {
      showError(getErrorMessage(err, "Could not open academic session."));
    } finally {
      setOpeningSessionId("");
    }
  };

  const saveTerm = async (event) => {
    event.preventDefault();
    setSaving("term");
    try {
      const payload = {
        academic_session_id: termForm.academic_session_id,
        name: termForm.name,
        start_date: termForm.start_date || null,
        end_date: termForm.end_date || null,
        is_current: termForm.is_current,
        is_active: termForm.is_active,
      };
      if (editing.type === "term") {
        await academicService.updateTerm(editing.id, payload);
      } else {
        await academicService.createTerm(payload);
      }
      showSuccess(
        editing.type === "term" ? "Academic term updated." : "Academic term created.",
      );
      resetTerm();
      await loadWorkspace();
    } catch (err) {
      showError(getErrorMessage(err, "Could not save academic term."));
    } finally {
      setSaving("");
    }
  };

  const saveScale = async (event) => {
    event.preventDefault();
    setSaving("scale");
    try {
      const payload = {
        grade: scaleForm.grade,
        min_score: Number(scaleForm.min_score),
        max_score: Number(scaleForm.max_score),
        remark: scaleForm.remark || null,
        is_active: scaleForm.is_active,
      };
      if (editing.type === "scale") {
        await academicService.updateGradingScale(editing.id, payload);
      } else {
        await academicService.createGradingScale(payload);
      }
      showSuccess(
        editing.type === "scale" ? "Grading scale updated." : "Grading scale created.",
      );
      resetScale();
      await loadWorkspace();
    } catch (err) {
      showError(getErrorMessage(err, "Could not save grading scale."));
    } finally {
      setSaving("");
    }
  };

  const saveSubject = async (event) => {
    event.preventDefault();
    setSaving("subject");
    try {
      const payload = {
        name: subjectForm.name,
        code: subjectForm.code || null,
        description: subjectForm.description || null,
      };
      if (editing.type === "subject") {
        await subjectService.updateSubject(editing.id, payload);
      } else {
        await subjectService.createSubject(payload);
      }
      showSuccess(
        editing.type === "subject" ? "Subject updated." : "Subject created.",
      );
      resetSubject();
      await loadWorkspace();
    } catch (err) {
      showError(getErrorMessage(err, "Could not save subject."));
    } finally {
      setSaving("");
    }
  };

  const periodsView = (
    <div className="space-y-4">
      <WorkspaceGrid
        editor={
          <WorkspacePanel
            title={editing.type === "session" ? "Edit session" : "Create session"}
            description="Session status is controlled explicitly with Open Session."
          >
            <form className="space-y-3" onSubmit={saveSession}>
              <Input
                label="Session name"
                value={sessionForm.name}
                onChange={(event) =>
                  setSessionForm((current) => ({ ...current, name: event.target.value }))
                }
                placeholder="2026/2027"
                minLength={9}
                maxLength={9}
                required
              />
              <div className="grid gap-3 sm:grid-cols-2">
                <Input
                  label="Start date"
                  type="date"
                  value={sessionForm.start_date}
                  onChange={(event) =>
                    setSessionForm((current) => ({
                      ...current,
                      start_date: event.target.value,
                    }))
                  }
                />
                <Input
                  label="End date"
                  type="date"
                  value={sessionForm.end_date}
                  onChange={(event) =>
                    setSessionForm((current) => ({
                      ...current,
                      end_date: event.target.value,
                    }))
                  }
                />
              </div>
              <SelectControl
                label="Next session"
                value={sessionForm.next_academic_session_id}
                onChange={(value) =>
                  setSessionForm((current) => ({
                    ...current,
                    next_academic_session_id: value,
                  }))
                }
                options={sessionOptions.filter((item) => item.value !== editing.id)}
                placeholder="Optional progression target"
              />
              <FormActions
                submitting={saving === "session"}
                submitLabel={editing.type === "session" ? "Update session" : "Create session"}
                editing={editing.type === "session"}
                onCancel={resetSession}
              />
            </form>
          </WorkspacePanel>
        }
        content={
          <WorkspacePanel
            title="Academic sessions"
            description="Only one session can be open and current at a time."
            actions={
              <Button type="button" variant="outline" size="small" onClick={loadWorkspace}>
                <RefreshCw className="h-4 w-4" /> Refresh
              </Button>
            }
          >
            <div className="space-y-3">
              {sessions.length === 0 ? (
                <p className="rounded-2xl border border-dashed border-border p-5 text-sm text-text-muted">
                  No academic sessions have been created.
                </p>
              ) : (
                sessions.map((item) => (
                  <div
                    key={item.id}
                    className="rounded-2xl border border-border/70 bg-surface px-4 py-4"
                  >
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="font-semibold text-text">{item.name}</p>
                          <Badge variant={item.is_current ? "success" : "default"}>
                            {item.status || (item.is_current ? "current" : "draft")}
                          </Badge>
                        </div>
                        <p className="mt-1 text-xs text-text-muted">
                          {dateLabel(item.start_date)} – {dateLabel(item.end_date)}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {!item.is_current && item.status !== "closed" ? (
                          <Button
                            type="button"
                            size="small"
                            onClick={() => openSession(item.id)}
                            disabled={Boolean(openingSessionId)}
                          >
                            {openingSessionId === item.id ? "Opening..." : "Open session"}
                          </Button>
                        ) : null}
                        <Button
                          type="button"
                          size="small"
                          variant="outline"
                          onClick={() => {
                            setEditing({ type: "session", id: item.id });
                            setSessionForm({
                              name: item.name || "",
                              start_date: item.start_date || "",
                              end_date: item.end_date || "",
                              next_academic_session_id:
                                item.next_academic_session_id || "",
                            });
                          }}
                        >
                          Edit
                        </Button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </WorkspacePanel>
        }
      />

      <WorkspaceGrid
        editor={
          <WorkspacePanel
            title={editing.type === "term" ? "Edit term" : "Create term"}
            description="Terms belong to a specific academic session."
          >
            <form className="space-y-3" onSubmit={saveTerm}>
              <SelectControl
                label="Academic session"
                value={termForm.academic_session_id}
                onChange={(value) =>
                  setTermForm((current) => ({ ...current, academic_session_id: value }))
                }
                options={sessionOptions}
                required
              />
              <SelectControl
                label="Term"
                value={termForm.name}
                onChange={(value) =>
                  setTermForm((current) => ({ ...current, name: value }))
                }
                options={[
                  { value: "first_term", label: "First Term" },
                  { value: "second_term", label: "Second Term" },
                  { value: "third_term", label: "Third Term" },
                ]}
                required
              />
              <div className="grid gap-3 sm:grid-cols-2">
                <Input
                  label="Start date"
                  type="date"
                  value={termForm.start_date}
                  onChange={(event) =>
                    setTermForm((current) => ({ ...current, start_date: event.target.value }))
                  }
                />
                <Input
                  label="End date"
                  type="date"
                  value={termForm.end_date}
                  onChange={(event) =>
                    setTermForm((current) => ({ ...current, end_date: event.target.value }))
                  }
                />
              </div>
              <CheckboxControl
                label="Current term"
                checked={termForm.is_current}
                onChange={(value) =>
                  setTermForm((current) => ({ ...current, is_current: value }))
                }
              />
              <CheckboxControl
                label="Active"
                checked={termForm.is_active}
                onChange={(value) =>
                  setTermForm((current) => ({ ...current, is_active: value }))
                }
              />
              <FormActions
                submitting={saving === "term"}
                submitLabel={editing.type === "term" ? "Update term" : "Create term"}
                editing={editing.type === "term"}
                onCancel={resetTerm}
              />
            </form>
          </WorkspacePanel>
        }
        content={
          <RecordList
            title="Academic terms"
            description="Current and historical terms across sessions."
            items={terms}
            emptyIcon={CalendarDays}
            emptyTitle="No academic terms"
            emptyDescription="Create a term after creating an academic session."
            renderTitle={(item) => termLabel(item.name)}
            renderMeta={(item) =>
              sessions.find((session) => session.id === item.academic_session_id)?.name ||
              "Unknown session"
            }
            renderDescription={(item) => `${dateLabel(item.start_date)} – ${dateLabel(item.end_date)}`}
            renderStatus={(item) => (item.is_current ? "current" : item.is_active ? "active" : "inactive")}
            onEdit={(item) => {
              setEditing({ type: "term", id: item.id });
              setTermForm({
                academic_session_id: item.academic_session_id || "",
                name: item.name || "first_term",
                start_date: item.start_date || "",
                end_date: item.end_date || "",
                is_current: Boolean(item.is_current),
                is_active: item.is_active !== false,
              });
            }}
          />
        }
      />
    </div>
  );

  const gradingView = (
    <WorkspaceGrid
      editor={
        <WorkspacePanel
          title={editing.type === "scale" ? "Edit grading scale" : "Create grading scale"}
          description="Score ranges may not overlap and must remain between 0 and 100."
        >
          <form className="space-y-3" onSubmit={saveScale}>
            <Input
              label="Grade"
              value={scaleForm.grade}
              onChange={(event) =>
                setScaleForm((current) => ({ ...current, grade: event.target.value }))
              }
              placeholder="A"
              required
            />
            <div className="grid gap-3 sm:grid-cols-2">
              <Input
                label="Minimum score"
                type="number"
                min="0"
                max="100"
                value={scaleForm.min_score}
                onChange={(event) =>
                  setScaleForm((current) => ({ ...current, min_score: event.target.value }))
                }
                required
              />
              <Input
                label="Maximum score"
                type="number"
                min="0"
                max="100"
                value={scaleForm.max_score}
                onChange={(event) =>
                  setScaleForm((current) => ({ ...current, max_score: event.target.value }))
                }
                required
              />
            </div>
            <Input
              label="Remark"
              value={scaleForm.remark}
              onChange={(event) =>
                setScaleForm((current) => ({ ...current, remark: event.target.value }))
              }
              placeholder="Excellent"
            />
            <CheckboxControl
              label="Active scale"
              checked={scaleForm.is_active}
              onChange={(value) =>
                setScaleForm((current) => ({ ...current, is_active: value }))
              }
            />
            <FormActions
              submitting={saving === "scale"}
              submitLabel={editing.type === "scale" ? "Update scale" : "Create scale"}
              editing={editing.type === "scale"}
              onCancel={resetScale}
            />
          </form>
        </WorkspacePanel>
      }
      content={
        <RecordList
          title="Grading scales"
          description="The active grade boundaries used when computing results."
          items={scales}
          emptyIcon={GraduationCap}
          emptyTitle="No grading scales"
          emptyDescription="Add grade boundaries before publishing results."
          renderTitle={(item) => item.grade}
          renderMeta={(item) => `${item.min_score} – ${item.max_score}`}
          renderDescription={(item) => item.remark || "No remark"}
          renderStatus={(item) => (item.is_active ? "active" : "inactive")}
          onEdit={(item) => {
            setEditing({ type: "scale", id: item.id });
            setScaleForm({
              grade: item.grade || "",
              min_score: item.min_score ?? "",
              max_score: item.max_score ?? "",
              remark: item.remark || "",
              is_active: item.is_active !== false,
            });
          }}
        />
      }
    />
  );

  const subjectsView = (
    <WorkspaceGrid
      editor={
        <WorkspacePanel
          title={editing.type === "subject" ? "Edit subject" : "Create subject"}
          description="Create each tenant-scoped subject once, then attach it to classes."
        >
          <form className="space-y-3" onSubmit={saveSubject}>
            <Input
              label="Subject name"
              value={subjectForm.name}
              onChange={(event) =>
                setSubjectForm((current) => ({ ...current, name: event.target.value }))
              }
              required
            />
            <Input
              label="Subject code"
              value={subjectForm.code}
              onChange={(event) =>
                setSubjectForm((current) => ({ ...current, code: event.target.value }))
              }
              placeholder="MTH"
            />
            <Input
              label="Description"
              value={subjectForm.description}
              onChange={(event) =>
                setSubjectForm((current) => ({
                  ...current,
                  description: event.target.value,
                }))
              }
            />
            <FormActions
              submitting={saving === "subject"}
              submitLabel={editing.type === "subject" ? "Update subject" : "Create subject"}
              editing={editing.type === "subject"}
              onCancel={resetSubject}
            />
          </form>
        </WorkspacePanel>
      }
      content={
        <RecordList
          title="Subject catalog"
          description="Subjects available for attachment to one or more classes."
          items={subjects}
          emptyIcon={BookOpen}
          emptyTitle="No subjects"
          emptyDescription="Create the first subject in this school workspace."
          renderTitle={(item) => item.name}
          renderMeta={(item) => item.code || "No code"}
          renderDescription={(item) => item.description || "No description"}
          renderStatus={(item) => (item.is_active === false ? "inactive" : "active")}
          onEdit={(item) => {
            setEditing({ type: "subject", id: item.id });
            setSubjectForm({
              name: item.name || "",
              code: item.code || "",
              description: item.description || "",
            });
          }}
        />
      }
    />
  );

  if (error && !loading) {
    return (
      <WorkspacePanel title="Academic setup unavailable">
        <p className="text-sm text-error">{error}</p>
        <Button type="button" className="mt-4" onClick={loadWorkspace}>
          Retry
        </Button>
      </WorkspacePanel>
    );
  }

  if (activeTab === "grading") return gradingView;
  if (activeTab === "subjects") return subjectsView;
  return periodsView;
}

export default AcademicSetupWorkspace;
