import { BookOpen, CalendarDays, GraduationCap } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import { useToast } from "../../hooks/useToast";
import { getErrorMessage } from "../../services/api";
import { academicService } from "../../services/academicService";
import { subjectService } from "../../services/subject.service";
import TypedConfirmationDialog from "./TypedConfirmationDialog";
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
const CONFIRM_OPEN_SESSION = "OPEN_ACADEMIC_SESSION";
const CONFIRM_CLOSE_SESSION = "CLOSE_AND_PROGRESS";
const CONFIRM_OPEN_TERM = "OPEN_ACADEMIC_TERM";
const CONFIRM_CLOSE_TERM = "CLOSE_ACADEMIC_TERM";

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

function AcademicSetupWorkspace({ activeTab, onContextChange, domain = "sessions" }) {
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
  const [closingSessionId, setClosingSessionId] = useState("");
  const [pendingConfirmation, setPendingConfirmation] = useState(null);
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
          subjectService.getSubjects({ limit: 100, includeArchived: domain === "subjects" }),
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
  }, [domain, onContextChange, showError]);

  useEffect(() => {
    loadWorkspace();
  }, [loadWorkspace]);

  const sessionOptions = useMemo(
    () => sessions.map((item) => ({ value: item.id, label: item.name })),
    [sessions],
  );
  const visibleSessions = useMemo(
    () =>
      activeTab === "draft"
        ? sessions.filter((item) => item.status === "draft")
        : activeTab === "open"
          ? sessions.filter((item) => item.status === "open")
          : activeTab === "closed"
            ? sessions.filter((item) => item.status === "closed")
            : sessions,
    [activeTab, sessions],
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

  const openSession = async (item) => {
    setOpeningSessionId(item.id);
    try {
      await academicService.openSession(item.id);
      showSuccess("Academic session opened.");
      await loadWorkspace();
    } catch (err) {
      showError(getErrorMessage(err, "Could not open academic session."));
    } finally {
      setOpeningSessionId("");
      setPendingConfirmation(null);
    }
  };

  const closeSessionAndProgress = async (item) => {
    setClosingSessionId(item.id);
    try {
      await academicService.closeSessionAndProgress(item.id, {
        idempotency_key: `session-close-${item.id}-${Date.now()}`,
      });
      showSuccess("Academic session closed and next session opened.");
      await loadWorkspace();
    } catch (err) {
      showError(getErrorMessage(err, "Could not close academic session."));
    } finally {
      setClosingSessionId("");
      setPendingConfirmation(null);
    }
  };

  const transitionTerm = async (item, transition) => {
    setSaving(item.id);
    try {
      if (transition === "open") {
        await academicService.openTerm(item.id);
        showSuccess("Academic term opened.");
      } else {
        await academicService.closeTerm(item.id);
        showSuccess("Academic term closed.");
      }
      await loadWorkspace();
    } catch (err) {
      showError(getErrorMessage(err, "Could not update academic term lifecycle."));
    } finally {
      setSaving("");
      setPendingConfirmation(null);
    }
  };

  const runConfirmedAction = () => {
    if (!pendingConfirmation) return;
    if (pendingConfirmation.type === "open-session") {
      openSession(pendingConfirmation.item);
      return;
    }
    if (pendingConfirmation.type === "close-session") {
      closeSessionAndProgress(pendingConfirmation.item);
      return;
    }
    if (pendingConfirmation.type === "term-transition") {
      transitionTerm(pendingConfirmation.item, pendingConfirmation.transition);
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

  const updateSubjectLifecycle = async (item, action) => {
    setSaving(item.id);
    try {
      if (action === "activate") await subjectService.activateSubject(item.id);
      if (action === "deactivate") await subjectService.deactivateSubject(item.id);
      if (action === "archive") await subjectService.archiveSubject(item.id);
      if (action === "restore") await subjectService.restoreSubject(item.id);
      showSuccess(`Subject ${action}d.`);
      await loadWorkspace();
    } catch (err) {
      showError(getErrorMessage(err, `Could not ${action} subject.`));
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
      {domain === "sessions" ? (
        <WorkspaceGrid
          editor={activeTab === "create" || editing.type === "session" ? (
            <WorkspacePanel
              title={editing.type === "session" ? "Edit session" : "Create session"}
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
          ) : null}
          content={activeTab === "create" ? null : (
            <WorkspacePanel
              title="Academic sessions"
            >
            <div className="space-y-3">
              {visibleSessions.length === 0 ? (
                <p className="rounded-2xl border border-dashed border-border p-5 text-sm text-text-muted">
                  No academic sessions have been created.
                </p>
              ) : (
                visibleSessions.map((item) => (
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
                        {item.next_academic_session_id ? (
                          <p className="mt-1 text-xs text-text-muted">
                            Next: {sessions.find((session) => session.id === item.next_academic_session_id)?.name || "Configured session"}
                          </p>
                        ) : null}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {item.status === "draft" ? (
                          <Button
                            type="button"
                            size="small"
                            onClick={() =>
                              setPendingConfirmation({
                                type: "open-session",
                                item,
                                title: "Open academic session",
                                description: item.name,
                                confirmationText: CONFIRM_OPEN_SESSION,
                                confirmLabel: "Open session",
                                variant: "primary",
                              })
                            }
                            disabled={Boolean(openingSessionId)}
                          >
                            {openingSessionId === item.id ? "Opening..." : "Open session"}
                          </Button>
                        ) : null}
                        {item.status === "open" && item.is_current ? (
                          <Button
                            type="button"
                            size="small"
                            variant="danger"
                            onClick={() =>
                              setPendingConfirmation({
                                type: "close-session",
                                item,
                                title: "Close academic session",
                                description: `${item.name} -> ${
                                  sessions.find((session) => session.id === item.next_academic_session_id)?.name ||
                                  "next configured session"
                                }`,
                                confirmationText: CONFIRM_CLOSE_SESSION,
                                confirmLabel: "Close and progress",
                                variant: "danger",
                              })
                            }
                            disabled={Boolean(closingSessionId) || !item.next_academic_session_id}
                          >
                            {closingSessionId === item.id ? "Closing..." : "Close and progress"}
                          </Button>
                        ) : null}
                        {!["closing", "closed"].includes(item.status) ? (
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
                        ) : null}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
            </WorkspacePanel>
          )}
        />
      ) : null}

      {domain === "terms" ? (
        <WorkspaceGrid
          editor={activeTab === "create" || editing.type === "term" ? (
            <WorkspacePanel
              title={editing.type === "term" ? "Edit term" : "Create term"}
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
              <FormActions
                submitting={saving === "term"}
                submitLabel={editing.type === "term" ? "Update term" : "Create term"}
                editing={editing.type === "term"}
                onCancel={resetTerm}
              />
            </form>
            </WorkspacePanel>
          ) : null}
          content={activeTab === "create" ? null : (
            <RecordList
              title="Academic terms"
            items={
              activeTab === "draft"
                ? terms.filter((item) => item.status === "draft")
                : activeTab === "open"
                  ? terms.filter((item) => item.status === "open")
                  : activeTab === "closed"
                    ? terms.filter((item) => item.status === "closed")
                    : terms
            }
            emptyIcon={CalendarDays}
            emptyTitle="No academic terms"
            emptyDescription="Create a term after creating an academic session."
            renderTitle={(item) => termLabel(item.name)}
            renderMeta={(item) =>
              sessions.find((session) => session.id === item.academic_session_id)?.name ||
              "Unknown session"
            }
            renderDescription={(item) => `${dateLabel(item.start_date)} – ${dateLabel(item.end_date)}`}
            renderStatus={(item) => (item.is_current ? "current" : item.status)}
            onEdit={(item) => {
              setEditing({ type: "term", id: item.id });
              setTermForm({
                academic_session_id: item.academic_session_id || "",
                name: item.name || "first_term",
                start_date: item.start_date || "",
                end_date: item.end_date || "",
              });
            }}
            actions={
              <div className="flex flex-wrap gap-2">
                {terms
                  .filter((item) => ["draft", "open"].includes(item.status))
                  .slice(0, 3)
                  .map((item) => (
                    <Button
                      key={item.id}
                      type="button"
                      size="small"
                      variant="outline"
                      disabled={saving === item.id}
                      onClick={() => {
                        const transition = item.status === "draft" ? "open" : "close";
                        setPendingConfirmation({
                          type: "term-transition",
                          item,
                          transition,
                          title: `${transition === "open" ? "Open" : "Close"} academic term`,
                          description: `${termLabel(item.name)} - ${
                            sessions.find((session) => session.id === item.academic_session_id)?.name ||
                            "Unknown session"
                          }`,
                          confirmationText:
                            transition === "open" ? CONFIRM_OPEN_TERM : CONFIRM_CLOSE_TERM,
                          confirmLabel: transition === "open" ? "Open term" : "Close term",
                          variant: transition === "open" ? "primary" : "danger",
                        });
                      }}
                    >
                      {item.status === "draft" ? "Open" : "Close"} {termLabel(item.name)}
                    </Button>
                  ))}
              </div>
            }
            />
          )}
        />
      ) : null}

      <TypedConfirmationDialog
        open={Boolean(pendingConfirmation)}
        title={pendingConfirmation?.title}
        description={pendingConfirmation?.description}
        confirmationText={pendingConfirmation?.confirmationText || ""}
        confirmLabel={pendingConfirmation?.confirmLabel}
        variant={pendingConfirmation?.variant}
        isLoading={
          pendingConfirmation?.type === "open-session"
            ? openingSessionId === pendingConfirmation.item?.id
            : pendingConfirmation?.type === "close-session"
              ? closingSessionId === pendingConfirmation.item?.id
              : saving === pendingConfirmation?.item?.id
        }
        onConfirm={runConfirmedAction}
        onCancel={() => setPendingConfirmation(null)}
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
          items={
            activeTab === "active"
              ? scales.filter((item) => item.is_active)
              : activeTab === "inactive"
                ? scales.filter((item) => !item.is_active)
                : scales
          }
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

  const gradingListView = (
    <RecordList
      title="Grading scales"
      description="The grade boundaries used when computing results."
      items={
        activeTab === "active"
          ? scales.filter((item) => item.is_active)
          : activeTab === "inactive"
            ? scales.filter((item) => !item.is_active)
            : scales
      }
      emptyIcon={GraduationCap}
      emptyTitle="No grading scales"
      emptyDescription="Create grade boundaries before publishing results."
      renderTitle={(item) => item.grade}
      renderMeta={(item) => `${item.min_score} - ${item.max_score}`}
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
          items={
            activeTab === "active"
              ? subjects.filter((item) => item.is_active !== false && !item.archived_at)
              : activeTab === "inactive"
                ? subjects.filter((item) => item.is_active === false && !item.archived_at)
                : activeTab === "archived"
                  ? subjects.filter((item) => item.archived_at)
                  : subjects.filter((item) => !item.archived_at)
          }
          emptyIcon={BookOpen}
          emptyTitle="No subjects"
          emptyDescription="Create the first subject in this school workspace."
          renderTitle={(item) => item.name}
          renderMeta={(item) => item.code || "No code"}
          renderDescription={(item) => item.description || "No description"}
          renderStatus={(item) => (item.is_active === false ? "inactive" : "active")}
          renderActions={(item) => (
            <>
              {item.archived_at ? (
                <Button
                  type="button"
                  size="small"
                  variant="outline"
                  disabled={saving === item.id}
                  onClick={() => updateSubjectLifecycle(item, "restore")}
                >
                  Restore
                </Button>
              ) : item.is_active === false ? (
                <Button
                  type="button"
                  size="small"
                  variant="success"
                  disabled={saving === item.id}
                  onClick={() => updateSubjectLifecycle(item, "activate")}
                >
                  Activate
                </Button>
              ) : (
                <Button
                  type="button"
                  size="small"
                  variant="outline"
                  disabled={saving === item.id}
                  onClick={() => updateSubjectLifecycle(item, "deactivate")}
                >
                  Deactivate
                </Button>
              )}
              {!item.archived_at ? (
                <Button
                  type="button"
                  size="small"
                  variant="danger"
                  disabled={saving === item.id}
                  onClick={() => updateSubjectLifecycle(item, "archive")}
                >
                  Archive
                </Button>
              ) : null}
            </>
          )}
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

  const subjectsCreateView = (
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
  );

  const subjectListItems =
    activeTab === "active"
      ? subjects.filter((item) => item.is_active !== false && !item.archived_at)
      : activeTab === "inactive"
        ? subjects.filter((item) => item.is_active === false && !item.archived_at)
        : activeTab === "archived"
          ? subjects.filter((item) => item.archived_at)
          : subjects.filter((item) => !item.archived_at);

  const subjectsListView = (
    <RecordList
      title="Subject catalog"
      description="Subjects available for attachment to one or more classes."
      items={subjectListItems}
      emptyIcon={BookOpen}
      emptyTitle="No subjects"
      emptyDescription="Create the first subject in this school workspace."
      renderTitle={(item) => item.name}
      renderMeta={(item) => item.code || "No code"}
      renderDescription={(item) => item.description || "No description"}
      renderStatus={(item) => (item.is_active === false ? "inactive" : "active")}
      renderActions={(item) => (
        <>
          {item.archived_at ? (
            <Button
              type="button"
              size="small"
              variant="outline"
              disabled={saving === item.id}
              onClick={() => updateSubjectLifecycle(item, "restore")}
            >
              Restore
            </Button>
          ) : item.is_active === false ? (
            <Button
              type="button"
              size="small"
              variant="success"
              disabled={saving === item.id}
              onClick={() => updateSubjectLifecycle(item, "activate")}
            >
              Activate
            </Button>
          ) : (
            <Button
              type="button"
              size="small"
              variant="outline"
              disabled={saving === item.id}
              onClick={() => updateSubjectLifecycle(item, "deactivate")}
            >
              Deactivate
            </Button>
          )}
          {!item.archived_at ? (
            <Button
              type="button"
              size="small"
              variant="danger"
              disabled={saving === item.id}
              onClick={() => updateSubjectLifecycle(item, "archive")}
            >
              Archive
            </Button>
          ) : null}
        </>
      )}
      onEdit={(item) => {
        setEditing({ type: "subject", id: item.id });
        setSubjectForm({
          name: item.name || "",
          code: item.code || "",
          description: item.description || "",
        });
      }}
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

  if (domain === "subjects") {
    if (activeTab === "create") return subjectsCreateView;
    if (editing.type === "subject") return subjectsView;
    return subjectsListView;
  }
  if (domain === "grading") {
    return activeTab === "create" || editing.type === "scale"
      ? gradingView
      : gradingListView;
  }
  if (domain === "terms") return activeTab === "create" ? periodsView : periodsView;
  if (domain === "sessions") return periodsView;
  if (activeTab === "grading") return gradingView;
  if (activeTab === "subjects") return subjectsView;
  return periodsView;
}

export default AcademicSetupWorkspace;
