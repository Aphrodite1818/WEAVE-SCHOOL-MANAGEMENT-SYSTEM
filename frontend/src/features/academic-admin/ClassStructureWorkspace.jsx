import { BookOpen, Library } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import { useToast } from "../../hooks/useToast";
import { classService } from "../../services/academicsService";
import { academicService } from "../../services/academicService";
import { getErrorMessage } from "../../services/api";
import { subjectService } from "../../services/subject.service";
import { teacherService } from "../../services/teacherService";
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

const BLANK_CLASS = {
  name: "",
  arm: "",
  teacher_membership_id: "",
};
const CONFIRM_ARCHIVE_CLASS_SUBJECT = "ARCHIVE_CLASS_SUBJECT";
const CONFIRM_RESTORE_CLASS_SUBJECT = "RESTORE_CLASS_SUBJECT";

const asItems = (response) =>
  Array.isArray(response)
    ? response
    : Array.isArray(response?.items)
      ? response.items
      : [];

const classLabel = (item) =>
  [item?.name, item?.arm].filter(Boolean).join(" ") || "Unnamed class";

const teacherLabel = (item) => {
  const account = item?.teacher_account || item?.account || {};
  const name = [account.first_name, account.last_name].filter(Boolean).join(" ");
  return name || account.email || item?.teacher_name || item?.staff_id || "Teacher";
};

function ClassStructureWorkspace({ activeTab, domain = "classes" }) {
  const [classes, setClasses] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [selectedClassId, setSelectedClassId] = useState("");
  const [mappingSelectedClassByTab, setMappingSelectedClassByTab] = useState({});
  const [classSubjects, setClassSubjects] = useState([]);
  const [classForm, setClassForm] = useState(BLANK_CLASS);
  const [subjectSelection, setSubjectSelection] = useState({
    subject_id: "",
    is_core: true,
  });
  const [editingClassId, setEditingClassId] = useState("");
  const [pendingMappingConfirmation, setPendingMappingConfirmation] = useState(null);
  const [saving, setSaving] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const { showSuccess, showError, showWarning } = useToast();

  const loadBase = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [classResponse, subjectResponse, teacherResponse] = await Promise.all([
        classService.getClasses({ limit: 100, includeArchived: domain === "classes" }),
        subjectService.getSubjects({ limit: 100, isActive: true }),
        teacherService.listMemberships({ limit: 100 }),
      ]);
      const nextClasses = asItems(classResponse);
      setClasses(nextClasses);
      setSubjects(asItems(subjectResponse));
      setTeachers(
        asItems(teacherResponse).filter((item) =>
          ["active", "read_only"].includes(String(item.status || "active").toLowerCase()),
        ),
      );
      if (domain !== "class-subjects") {
        setSelectedClassId((current) => current || nextClasses[0]?.id || "");
      }
    } catch (err) {
      const message = getErrorMessage(err, "Could not load class structure.");
      setError(message);
      showError(message);
    } finally {
      setLoading(false);
    }
  }, [domain, showError]);

  const activeSelectedClassId =
    domain === "class-subjects"
      ? mappingSelectedClassByTab[activeTab] || ""
      : selectedClassId;

  const setActiveSelectedClassId = useCallback(
    (value) => {
      if (domain === "class-subjects") {
        setMappingSelectedClassByTab((current) => ({
          ...current,
          [activeTab]: value,
        }));
        return;
      }
      setSelectedClassId(value);
    },
    [activeTab, domain],
  );

  useEffect(() => {
    if (domain !== "class-subjects" || activeSelectedClassId || classes.length === 0) {
      return;
    }
    setMappingSelectedClassByTab((current) => ({
      ...current,
      [activeTab]: current[activeTab] || classes[0]?.id || "",
    }));
  }, [activeSelectedClassId, activeTab, classes, domain]);

  const loadClassSubjects = useCallback(async () => {
    if (!activeSelectedClassId) {
      setClassSubjects([]);
      return;
    }
    try {
      const response = await academicService.listOfferedClassSubjects(
        activeSelectedClassId,
        { active_only: false, limit: 100 },
      );
      setClassSubjects(asItems(response));
    } catch (err) {
      setClassSubjects([]);
      showError(getErrorMessage(err, "Could not load subjects for this class."));
    }
  }, [activeSelectedClassId, showError]);

  useEffect(() => {
    loadBase();
  }, [loadBase]);

  useEffect(() => {
    loadClassSubjects();
  }, [loadClassSubjects]);

  const classOptions = useMemo(
    () => classes.map((item) => ({ value: item.id, label: classLabel(item) })),
    [classes],
  );
  const teacherOptions = useMemo(
    () => teachers.map((item) => ({ value: item.id, label: teacherLabel(item) })),
    [teachers],
  );
  const offeredSubjectIds = useMemo(
    () => new Set(classSubjects.filter((item) => item.is_active).map((item) => item.subject_id)),
    [classSubjects],
  );
  const subjectOptions = useMemo(
    () =>
      subjects
        .filter((item) => !offeredSubjectIds.has(item.id))
        .map((item) => ({
          value: item.id,
          label: [item.name, item.code].filter(Boolean).join(" · "),
        })),
    [offeredSubjectIds, subjects],
  );

  const resetClassForm = () => {
    setClassForm(BLANK_CLASS);
    setEditingClassId("");
  };

  const saveClass = async (event) => {
    event.preventDefault();
    setSaving("class");
    try {
      const payload = {
        name: classForm.name,
        arm: classForm.arm || null,
        teacher_membership_id: classForm.teacher_membership_id || null,
      };
      if (editingClassId) {
        await classService.updateClass(editingClassId, payload);
      } else {
        await classService.createClass(payload);
      }
      showSuccess(editingClassId ? "Class updated." : "Class created.");
      resetClassForm();
      await loadBase();
    } catch (err) {
      showError(getErrorMessage(err, "Could not save class."));
    } finally {
      setSaving("");
    }
  };

  const attachSubject = async (event) => {
    event.preventDefault();
    if (!activeSelectedClassId || !subjectSelection.subject_id) {
      showWarning("Select a class and subject first.");
      return;
    }
    setSaving("offering");
    try {
      await academicService.addClassSubject(activeSelectedClassId, {
        subject_id: subjectSelection.subject_id,
        is_core: subjectSelection.is_core,
      });
      showSuccess("Subject attached to class.");
      setSubjectSelection({ subject_id: "", is_core: true });
      await loadClassSubjects();
    } catch (err) {
      showError(getErrorMessage(err, "Could not attach subject to class."));
    } finally {
      setSaving("");
    }
  };

  const deactivateOffering = async (item) => {
    setSaving(item.id);
    try {
      await academicService.deactivateClassSubject(item.id);
      showSuccess("Class subject deactivated.");
      await loadClassSubjects();
    } catch (err) {
      showError(getErrorMessage(err, "Could not deactivate class subject."));
    } finally {
      setSaving("");
    }
  };

  const updateClassLifecycle = async (item, action) => {
    setSaving(item.id);
    try {
      if (action === "activate") await classService.activateClass(item.id);
      if (action === "deactivate") await classService.deactivateClass(item.id);
      if (action === "archive") await classService.archiveClass(item.id);
      if (action === "restore") await classService.restoreClass(item.id);
      showSuccess(`Class ${action}d.`);
      await loadBase();
    } catch (err) {
      showError(getErrorMessage(err, `Could not ${action} class.`));
    } finally {
      setSaving("");
      setPendingMappingConfirmation(null);
    }
  };

  const updateMappingLifecycle = async (item, action) => {
    setSaving(item.id);
    try {
      if (action === "activate") await academicService.activateClassSubject(activeSelectedClassId, item.id);
      if (action === "deactivate") await academicService.deactivateClassSubject(item.id);
      if (action === "archive") await academicService.archiveClassSubject(item.id);
      if (action === "restore") await academicService.restoreClassSubject(item.id);
      showSuccess(`Class-subject mapping ${action}d.`);
      await loadClassSubjects();
    } catch (err) {
      showError(getErrorMessage(err, `Could not ${action} class-subject mapping.`));
    } finally {
      setSaving("");
    }
  };

  const classesView = (
    <WorkspaceGrid
      editor={
        <WorkspacePanel
          title={editingClassId ? "Edit class" : "Create class"}
          description="Class level is represented by the class name; no separate level field is used."
        >
          <form className="space-y-3" onSubmit={saveClass}>
            <Input
              label="Class name"
              value={classForm.name}
              onChange={(event) =>
                setClassForm((current) => ({ ...current, name: event.target.value }))
              }
              placeholder="JSS 1"
              required
            />
            <Input
              label="Arm"
              value={classForm.arm}
              onChange={(event) =>
                setClassForm((current) => ({ ...current, arm: event.target.value }))
              }
              placeholder="A"
            />
            <SelectControl
              label="Class teacher"
              value={classForm.teacher_membership_id}
              onChange={(value) =>
                setClassForm((current) => ({
                  ...current,
                  teacher_membership_id: value,
                }))
              }
              options={teacherOptions}
              placeholder="Optional class teacher"
            />
            <FormActions
              submitting={saving === "class"}
              submitLabel={editingClassId ? "Update class" : "Create class"}
              editing={Boolean(editingClassId)}
              onCancel={resetClassForm}
            />
          </form>
        </WorkspacePanel>
      }
      content={
        <RecordList
          title="Classes"
          description="Active and inactive classes in this school workspace."
          items={
            activeTab === "active"
              ? classes.filter((item) => item.is_active && !item.archived_at)
              : activeTab === "inactive"
                ? classes.filter((item) => !item.is_active && !item.archived_at)
                : activeTab === "archived"
                  ? classes.filter((item) => item.archived_at)
                  : classes.filter((item) => !item.archived_at)
          }
          emptyIcon={Library}
          emptyTitle="No classes"
          emptyDescription="Create the first class before adding students or subject offerings."
          renderTitle={classLabel}
          renderMeta={(item) =>
            item.teacher_membership_id
              ? teacherLabel(teachers.find((teacher) => teacher.id === item.teacher_membership_id))
              : "No class teacher"
          }
          renderDescription={(item) =>
            item.is_terminal
              ? "Terminal class"
              : item.next_class_id
                ? `Progresses to ${classLabel(classes.find((entry) => entry.id === item.next_class_id))}`
                : "Progression target not configured"
          }
          renderStatus={(item) => (item.archived_at ? "archived" : item.is_active ? "active" : "inactive")}
          renderActions={(item) => (
            <>
              {item.archived_at ? (
                <Button
                  type="button"
                  size="small"
                  variant="outline"
                  disabled={saving === item.id}
                  onClick={() => updateClassLifecycle(item, "restore")}
                >
                  Restore
                </Button>
              ) : item.is_active ? (
                <Button
                  type="button"
                  size="small"
                  variant="outline"
                  disabled={saving === item.id}
                  onClick={() => updateClassLifecycle(item, "deactivate")}
                >
                  Deactivate
                </Button>
              ) : (
                <Button
                  type="button"
                  size="small"
                  variant="success"
                  disabled={saving === item.id}
                  onClick={() => updateClassLifecycle(item, "activate")}
                >
                  Activate
                </Button>
              )}
              {!item.archived_at ? (
                <Button
                  type="button"
                  size="small"
                  variant="danger"
                  disabled={saving === item.id}
                  onClick={() => updateClassLifecycle(item, "archive")}
                >
                  Archive
                </Button>
              ) : null}
            </>
          )}
          onEdit={(item) => {
            setEditingClassId(item.id);
            setClassForm({
              name: item.name || "",
              arm: item.arm || "",
              teacher_membership_id: item.teacher_membership_id || "",
            });
          }}
        />
      }
    />
  );

  const classCreateView = (
    <WorkspacePanel
      title={editingClassId ? "Edit class" : "Create class"}
      description="Class level is represented by the class name; no separate level field is used."
    >
      <form className="space-y-3" onSubmit={saveClass}>
        <Input
          label="Class name"
          value={classForm.name}
          onChange={(event) =>
            setClassForm((current) => ({ ...current, name: event.target.value }))
          }
          placeholder="JSS 1"
          required
        />
        <Input
          label="Arm"
          value={classForm.arm}
          onChange={(event) =>
            setClassForm((current) => ({ ...current, arm: event.target.value }))
          }
          placeholder="A"
        />
        <SelectControl
          label="Class teacher"
          value={classForm.teacher_membership_id}
          onChange={(value) =>
            setClassForm((current) => ({
              ...current,
              teacher_membership_id: value,
            }))
          }
          options={teacherOptions}
          placeholder="Optional class teacher"
        />
        <FormActions
          submitting={saving === "class"}
          submitLabel={editingClassId ? "Update class" : "Create class"}
          editing={Boolean(editingClassId)}
          onCancel={resetClassForm}
        />
      </form>
    </WorkspacePanel>
  );

  const classListItems =
    activeTab === "active"
      ? classes.filter((item) => item.is_active && !item.archived_at)
      : activeTab === "inactive"
        ? classes.filter((item) => !item.is_active && !item.archived_at)
        : activeTab === "archived"
          ? classes.filter((item) => item.archived_at)
          : classes;

  const classListView = (
    <RecordList
      title="Classes"
      description="Classes in this school workspace."
      items={classListItems}
      emptyIcon={Library}
      emptyTitle="No classes"
      emptyDescription="Create the first class before adding students or subject offerings."
      renderTitle={classLabel}
      renderMeta={(item) =>
        item.teacher_membership_id
          ? teacherLabel(teachers.find((teacher) => teacher.id === item.teacher_membership_id))
          : "No class teacher"
      }
      renderDescription={(item) =>
        item.is_terminal
          ? "Terminal class"
          : item.next_class_id
            ? `Progresses to ${classLabel(classes.find((entry) => entry.id === item.next_class_id))}`
            : "Progression target not configured"
      }
      renderStatus={(item) => (item.archived_at ? "archived" : item.is_active ? "active" : "inactive")}
      renderActions={(item) => (
        <>
          {item.archived_at ? (
            <Button
              type="button"
              size="small"
              variant="outline"
              disabled={saving === item.id}
              onClick={() => updateClassLifecycle(item, "restore")}
            >
              Restore
            </Button>
          ) : item.is_active ? (
            <Button
              type="button"
              size="small"
              variant="outline"
              disabled={saving === item.id}
              onClick={() => updateClassLifecycle(item, "deactivate")}
            >
              Deactivate
            </Button>
          ) : (
            <Button
              type="button"
              size="small"
              variant="success"
              disabled={saving === item.id}
              onClick={() => updateClassLifecycle(item, "activate")}
            >
              Activate
            </Button>
          )}
          {!item.archived_at ? (
            <Button
              type="button"
              size="small"
              variant="danger"
              disabled={saving === item.id}
              onClick={() => updateClassLifecycle(item, "archive")}
            >
              Archive
            </Button>
          ) : null}
        </>
      )}
      onEdit={(item) => {
        setEditingClassId(item.id);
        setClassForm({
          name: item.name || "",
          arm: item.arm || "",
          teacher_membership_id: item.teacher_membership_id || "",
        });
      }}
    />
  );

  const offeringsView = (
    <>
      <WorkspaceGrid
      editor={activeTab === "create" ? (
        <WorkspacePanel
          title="Attach subject to class"
          description="A subject must exist in the catalog before it can be offered by a class."
        >
          <form className="space-y-3" onSubmit={attachSubject}>
            <SelectControl
              label="Class"
              value={activeSelectedClassId}
              onChange={setActiveSelectedClassId}
              options={classOptions}
              required
            />
            <SelectControl
              label="Subject"
              value={subjectSelection.subject_id}
              onChange={(value) =>
                setSubjectSelection((current) => ({ ...current, subject_id: value }))
              }
              options={subjectOptions}
              placeholder={
                subjectOptions.length === 0
                  ? "All active subjects are attached"
                  : "Select subject"
              }
              disabled={subjectOptions.length === 0}
              required
            />
            <CheckboxControl
              label="Core subject"
              checked={subjectSelection.is_core}
              onChange={(value) =>
                setSubjectSelection((current) => ({ ...current, is_core: value }))
              }
            />
            <Button
              type="submit"
              disabled={saving === "offering" || subjectOptions.length === 0}
            >
              {saving === "offering" ? "Attaching..." : "Attach subject"}
            </Button>
          </form>
        </WorkspacePanel>
      ) : null}
      content={activeTab === "create" ? null : (
        <WorkspacePanel
          title="Offered subjects"
          description={
            activeSelectedClassId
              ? `Subjects attached to ${classLabel(classes.find((item) => item.id === activeSelectedClassId))}.`
              : "Select a class to review its subjects."
          }
        >
          <div className="mb-4 max-w-md">
            <SelectControl
              label="Class"
              value={activeSelectedClassId}
              onChange={setActiveSelectedClassId}
              options={classOptions}
              placeholder="Select class"
              disabled={classOptions.length === 0}
            />
          </div>
          {classSubjects.length === 0 ? (
            <p className="rounded-2xl border border-dashed border-border p-5 text-sm text-text-muted">
              No subjects are attached to this class.
            </p>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">
              {classSubjects
                .filter((item) =>
                  activeTab === "inactive"
                    ? !item.is_active && !item.archived_at
                    : activeTab === "archived"
                      ? item.archived_at
                      : activeTab === "current" || activeTab === "create"
                        ? item.is_active && !item.archived_at
                        : true,
                )
                .map((item) => (
                <div
                  key={item.id}
                  className="flex min-h-[8rem] flex-col rounded-2xl border border-border/70 bg-surface px-4 py-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-semibold text-text">
                        {item.subject_name || "Subject"}
                      </p>
                      <p className="mt-1 text-xs text-text-muted">
                        {item.subject_code || "No code"}
                      </p>
                    </div>
                    <Badge variant={item.is_active ? "success" : "error"}>
                      {item.is_active ? "active" : "inactive"}
                    </Badge>
                  </div>
                  <p className="mt-3 text-sm text-text-muted">
                    {item.is_core ? "Core subject" : "Elective subject"}
                  </p>
                  <div className="mt-auto flex flex-wrap gap-2 pt-4">
                    {item.archived_at ? (
                      <Button
                        type="button"
                        size="small"
                        variant="outline"
                        disabled={saving === item.id}
                        onClick={() =>
                          setPendingMappingConfirmation({
                            item,
                            action: "restore",
                            title: "Restore class-subject mapping",
                            description: item.subject_name || "Class-subject mapping",
                            confirmationText: CONFIRM_RESTORE_CLASS_SUBJECT,
                            confirmLabel: "Restore mapping",
                            variant: "primary",
                          })
                        }
                      >
                        Restore
                      </Button>
                    ) : item.is_active ? (
                      <Button
                        type="button"
                        size="small"
                        variant="outline"
                        disabled={saving === item.id}
                        onClick={() => deactivateOffering(item)}
                      >
                        {saving === item.id ? "Removing..." : "Deactivate"}
                      </Button>
                    ) : (
                      <Button
                        type="button"
                        size="small"
                        variant="success"
                        disabled={saving === item.id}
                        onClick={() => updateMappingLifecycle(item, "activate")}
                      >
                        Activate
                      </Button>
                    )}
                    {!item.archived_at ? (
                      <Button
                        type="button"
                        size="small"
                        variant="danger"
                        disabled={saving === item.id}
                        onClick={() =>
                          setPendingMappingConfirmation({
                            item,
                            action: "archive",
                            title: "Archive class-subject mapping",
                            description: item.subject_name || "Class-subject mapping",
                            confirmationText: CONFIRM_ARCHIVE_CLASS_SUBJECT,
                            confirmLabel: "Archive mapping",
                            variant: "danger",
                          })
                        }
                      >
                        Archive
                      </Button>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          )}
        </WorkspacePanel>
      )}
      />
      <TypedConfirmationDialog
        open={Boolean(pendingMappingConfirmation)}
        title={pendingMappingConfirmation?.title}
        description={pendingMappingConfirmation?.description}
        confirmationText={pendingMappingConfirmation?.confirmationText || ""}
        confirmLabel={pendingMappingConfirmation?.confirmLabel}
        variant={pendingMappingConfirmation?.variant}
        isLoading={saving === pendingMappingConfirmation?.item?.id}
        onConfirm={() => {
          if (!pendingMappingConfirmation) return;
          updateMappingLifecycle(
            pendingMappingConfirmation.item,
            pendingMappingConfirmation.action,
          );
        }}
        onCancel={() => setPendingMappingConfirmation(null)}
      />
    </>
  );

  const reviewView = (
    <WorkspacePanel
      title="Academic structure review"
      description="A compact view of every class, its teacher, progression state, and offered subjects."
    >
      <div className="space-y-3">
        {classes.length === 0 ? (
          <p className="rounded-2xl border border-dashed border-border p-5 text-sm text-text-muted">
            No classes are available for review.
          </p>
        ) : (
          classes.map((item) => {
            const isSelected = item.id === activeSelectedClassId;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setActiveSelectedClassId(item.id)}
                className="w-full rounded-2xl border border-border/70 bg-surface px-4 py-4 text-left transition hover:border-primary/30 hover:bg-primary-subtle/20"
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="font-semibold text-text">{classLabel(item)}</p>
                    <p className="mt-1 text-sm text-text-muted">
                      {item.teacher_membership_id
                        ? `Class teacher: ${teacherLabel(
                            teachers.find(
                              (teacher) => teacher.id === item.teacher_membership_id,
                            ),
                          )}`
                        : "No class teacher assigned"}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Badge variant={item.is_active ? "success" : "error"}>
                      {item.is_active ? "active" : "inactive"}
                    </Badge>
                    {item.is_terminal ? <Badge variant="warning">terminal</Badge> : null}
                    {isSelected ? <Badge variant="primary">showing subjects</Badge> : null}
                  </div>
                </div>
              </button>
            );
          })
        )}
      </div>
      {activeSelectedClassId ? (
        <div className="mt-5 rounded-2xl border border-border/70 bg-surface-muted/25 p-4">
          <div className="flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-primary" />
            <p className="font-semibold text-text">
              {classLabel(classes.find((item) => item.id === activeSelectedClassId))} subjects
            </p>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {classSubjects.filter((item) => item.is_active).length === 0 ? (
              <span className="text-sm text-text-muted">No active subjects attached.</span>
            ) : (
              classSubjects
                .filter((item) => item.is_active)
                .map((item) => (
                  <Badge key={item.id} variant={item.is_core ? "primary" : "default"}>
                    {item.subject_name || "Subject"}
                  </Badge>
                ))
            )}
          </div>
        </div>
      ) : null}
    </WorkspacePanel>
  );

  if (error && !loading) {
    return (
      <WorkspacePanel title="Class structure unavailable">
        <p className="text-sm text-error">{error}</p>
        <Button type="button" className="mt-4" onClick={loadBase}>
          Retry
        </Button>
      </WorkspacePanel>
    );
  }

  if (domain === "class-subjects") {
    if (activeTab === "review") return reviewView;
    return activeTab === "create" ? offeringsView : offeringsView;
  }
  if (activeTab === "create") return classCreateView;
  if (activeTab === "offerings") return offeringsView;
  if (activeTab === "review") return reviewView;
  if (editingClassId) return classesView;
  return classListView;
}

export default ClassStructureWorkspace;
