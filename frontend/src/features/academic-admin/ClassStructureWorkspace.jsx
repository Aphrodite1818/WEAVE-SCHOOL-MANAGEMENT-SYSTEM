import { Library } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import MultiSelect from "../../components/ui/MultiSelect";
import { useToast } from "../../hooks/useToast";
import { classService } from "../../services/academicsService";
import { academicService } from "../../services/academicService";
import { getErrorMessage, parseApiError } from "../../services/api";
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
import { isAssignableClassTeacher } from "./classTeacherEligibility";

const BLANK_CLASS = {
  name: "",
  arm: "",
  teacher_membership_id: "",
};
const BLANK_PROGRESSION = {
  class_id: "",
  next_class_id: "",
  is_terminal: false,
};
const CONFIRM_ACTIVATE_CLASSROOM = "ACTIVATE_CLASSROOM";
const CONFIRM_DEACTIVATE_CLASSROOM = "DEACTIVATE_CLASSROOM";
const CONFIRM_ARCHIVE_CLASSROOM = "ARCHIVE_CLASSROOM";
const CONFIRM_RESTORE_CLASSROOM = "RESTORE_CLASSROOM";
const CONFIRM_ACTIVATE_CLASS_SUBJECT = "ACTIVATE_CLASS_SUBJECT";
const CONFIRM_DEACTIVATE_CLASS_SUBJECT = "DEACTIVATE_CLASS_SUBJECT";
const CONFIRM_ARCHIVE_CLASS_SUBJECT = "ARCHIVE_CLASS_SUBJECT";
const CONFIRM_RESTORE_CLASS_SUBJECT = "RESTORE_CLASS_SUBJECT";
const CONFIRM_DELETE_CLASS_SUBJECT = "DELETE_CLASS_SUBJECT";

const DEPENDENCY_LABELS = {
  active_teacher_assignments: "active teacher assignments",
  teacher_assignment_history: "teacher assignment history",
  student_results: "student results",
  report_card_lines: "report-card lines",
  compatibility_teacher_rows: "compatibility teacher rows",
  active_compatibility_teacher_rows: "active compatibility teacher rows",
};

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

const classLifecycleConfirmation = (item, action) => {
  const config = {
    activate: {
      title: "Activate class",
      confirmationText: CONFIRM_ACTIVATE_CLASSROOM,
      confirmLabel: "Activate class",
      variant: "primary",
    },
    deactivate: {
      title: "Deactivate class",
      confirmationText: CONFIRM_DEACTIVATE_CLASSROOM,
      confirmLabel: "Deactivate class",
      variant: "danger",
    },
    archive: {
      title: "Archive class",
      confirmationText: CONFIRM_ARCHIVE_CLASSROOM,
      confirmLabel: "Archive class",
      variant: "danger",
      description: `${classLabel(item)} must already be inactive. Historical records, results, attendance, and report cards will remain available.`,
    },
    restore: {
      title: "Restore class",
      confirmationText: CONFIRM_RESTORE_CLASSROOM,
      confirmLabel: "Restore class",
      variant: "primary",
    },
  }[action];

  return {
    item,
    action,
    description: config.description || classLabel(item),
    ...config,
  };
};

const formatMappingError = (error, fallback) => {
  const parsed = parseApiError(error, fallback);
  const counts = parsed.data?.dependency_counts;
  if (!counts || typeof counts !== "object") return parsed.message;

  const details = Object.entries(DEPENDENCY_LABELS)
    .map(([key, label]) => {
      const value = Number(counts[key] || 0);
      return value > 0 ? `${label}: ${value}` : null;
    })
    .filter(Boolean)
    .join("; ");

  return details ? `${parsed.message} ${details}.` : parsed.message;
};

const mappingLifecycleConfirmation = (item, action) => {
  const name = item.subject_name || "Subject in class";
  const config = {
    activate: {
      title: "Activate subject for this class",
      confirmationText: CONFIRM_ACTIVATE_CLASS_SUBJECT,
      confirmLabel: "Activate subject",
      variant: "primary",
      description: item.activation_blocker || name,
    },
    deactivate: {
      title: "Deactivate subject for this class",
      confirmationText: CONFIRM_DEACTIVATE_CLASS_SUBJECT,
      confirmLabel: "Deactivate subject",
      variant: "danger",
      description: `${name} will stop appearing in new academic work for this class. Existing records remain available.`,
    },
    archive: {
      title: "Archive subject for this class",
      confirmationText: CONFIRM_ARCHIVE_CLASS_SUBJECT,
      confirmLabel: "Archive subject",
      variant: "danger",
      description: `${name} must already be inactive. Academic history will remain available.`,
    },
    restore: {
      title: "Restore subject for this class",
      confirmationText: CONFIRM_RESTORE_CLASS_SUBJECT,
      confirmLabel: "Restore subject",
      variant: "primary",
      description: name,
    },
    delete: {
      title: "Remove subject from this class",
      confirmationText: CONFIRM_DELETE_CLASS_SUBJECT,
      confirmLabel: "Remove subject",
      variant: "danger",
      description: `${name} must be inactive, unarchived, and have no academic history.`,
    },
  }[action];

  return { item, action, ...config };
};

function ClassStructureWorkspace({ activeTab, domain = "classes" }) {
  const [classes, setClasses] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [classSearchDraft, setClassSearchDraft] = useState("");
  const [classSearch, setClassSearch] = useState("");
  const [selectedClassId, setSelectedClassId] = useState("");
  const [mappingSelectedClassByTab, setMappingSelectedClassByTab] = useState({});
  const [classSubjects, setClassSubjects] = useState([]);
  const [classForm, setClassForm] = useState(BLANK_CLASS);
  const [progressionForm, setProgressionForm] = useState(BLANK_PROGRESSION);
  const [subjectSelection, setSubjectSelection] = useState({
    subject_ids: [],
    is_core: true,
  });
  const [editingClassId, setEditingClassId] = useState("");
  const [viewingClass, setViewingClass] = useState(null);
  const [pendingClassConfirmation, setPendingClassConfirmation] = useState(null);
  const [pendingMappingConfirmation, setPendingMappingConfirmation] = useState(null);
  const [editingMapping, setEditingMapping] = useState(null);
  const [viewingMapping, setViewingMapping] = useState(null);
  const [reviewingClass, setReviewingClass] = useState(null);
  const [reviewClassSubjects, setReviewClassSubjects] = useState([]);
  const [reviewClassLoading, setReviewClassLoading] = useState(false);
  const [saving, setSaving] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const classLoadSequence = useRef(0);
  const { showSuccess, showError, showWarning } = useToast();

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const nextSearch = classSearchDraft.trim();
      setClassSearch((current) => (current === nextSearch ? current : nextSearch));
    }, 300);
    return () => window.clearTimeout(timer);
  }, [classSearchDraft]);

  const loadClasses = useCallback(async () => {
    const requestId = classLoadSequence.current + 1;
    classLoadSequence.current = requestId;
    setLoading(true);
    setError(null);
    try {
      const classResponse = await classService.getClasses({
        limit: 100,
        includeArchived: domain === "classes",
        search: classSearch || undefined,
      });
      if (classLoadSequence.current !== requestId) return;
      const nextClasses = asItems(classResponse);
      setClasses(nextClasses);
      if (domain !== "class-subjects") {
        setSelectedClassId((current) => current || nextClasses[0]?.id || "");
      }
    } catch (err) {
      if (classLoadSequence.current !== requestId) return;
      const message = getErrorMessage(err, "Could not load class structure.");
      setError(message);
      showError(message);
    } finally {
      if (classLoadSequence.current === requestId) setLoading(false);
    }
  }, [classSearch, domain, showError]);

  const loadLookups = useCallback(async () => {
    try {
      const [subjectResponse, teacherResponse] = await Promise.all([
        subjectService.getSubjects({ limit: 500, isActive: true }),
        teacherService.listMemberships({ limit: 100 }),
      ]);
      setSubjects(asItems(subjectResponse));
      setTeachers(asItems(teacherResponse).filter(isAssignableClassTeacher));
    } catch (err) {
      showError(getErrorMessage(err, "Could not load class structure lookups."));
    }
  }, [showError]);

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
        { active_only: false, include_archived: true, limit: 100 },
      );
      setClassSubjects(asItems(response));
    } catch (err) {
      setClassSubjects([]);
      showError(getErrorMessage(err, "Could not load subjects for this class."));
    }
  }, [activeSelectedClassId, showError]);

  useEffect(() => {
    loadLookups();
  }, [loadLookups]);

  useEffect(() => {
    loadClasses();
  }, [loadClasses]);

  useEffect(() => {
    loadClassSubjects();
  }, [loadClassSubjects]);

  const classOptions = useMemo(
    () => classes.map((item) => ({ value: item.id, label: classLabel(item) })),
    [classes],
  );
  const activeClassOptions = useMemo(
    () =>
      classes
        .filter((item) => item.is_active && !item.archived_at)
        .map((item) => ({ value: item.id, label: classLabel(item) })),
    [classes],
  );
  const progressionTargetOptions = useMemo(
    () =>
      activeClassOptions.filter((option) => option.value !== progressionForm.class_id),
    [activeClassOptions, progressionForm.class_id],
  );
  const teacherOptions = useMemo(
    () => teachers.map((item) => ({ value: item.id, label: teacherLabel(item) })),
    [teachers],
  );
  const offeredSubjectIds = useMemo(
    () => new Set(classSubjects.map((item) => item.subject_id)),
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
  const filteredClassSubjects = useMemo(
    () =>
      classSubjects.filter((item) =>
        activeTab === "inactive"
          ? !item.is_active && !item.archived_at
          : activeTab === "archived"
            ? item.archived_at
            : activeTab === "current" || activeTab === "create"
              ? item.is_active && !item.archived_at
              : true,
      ),
    [activeTab, classSubjects],
  );

  const mappingEmptyMessage =
    activeTab === "inactive"
      ? "No inactive subjects are attached to this class."
      : activeTab === "archived"
        ? "No archived subjects are attached to this class."
        : "No current subjects are attached to this class.";

  const resetClassForm = () => {
    setClassForm(BLANK_CLASS);
    setEditingClassId("");
  };

  const setProgressionSourceClass = (classId) => {
    const selectedClass = classes.find((item) => item.id === classId);
    setProgressionForm({
      class_id: classId,
      next_class_id: selectedClass?.next_class_id || "",
      is_terminal: Boolean(selectedClass?.is_terminal),
    });
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
      await loadClasses();
    } catch (err) {
      showError(getErrorMessage(err, "Could not save class."));
    } finally {
      setSaving("");
    }
  };

  const attachSubject = async (event) => {
    event.preventDefault();
    if (!activeSelectedClassId || subjectSelection.subject_ids.length === 0) {
      showWarning("Select a class and at least one subject first.");
      return;
    }
    setSaving("offering");
    try {
      const created = await academicService.addClassSubjectsBulk(activeSelectedClassId, {
        subject_ids: subjectSelection.subject_ids,
        is_core: subjectSelection.is_core,
      });
      const count = Array.isArray(created) ? created.length : subjectSelection.subject_ids.length;
      showSuccess(`${count} subject${count === 1 ? "" : "s"} attached to class.`);
      setSubjectSelection({ subject_ids: [], is_core: true });
      await loadClassSubjects();
    } catch (err) {
      showError(formatMappingError(err, "Could not attach subjects to class."));
    } finally {
      setSaving("");
    }
  };

  const saveClassProgression = async (event) => {
    event.preventDefault();
    if (!progressionForm.class_id) {
      showWarning("Select a class before configuring progression.");
      return;
    }
    if (!progressionForm.is_terminal && !progressionForm.next_class_id) {
      showWarning("Select a next class or mark this class as terminal.");
      return;
    }

    setSaving("progression");
    try {
      await classService.configureClassProgression(progressionForm.class_id, {
        next_class_id: progressionForm.next_class_id || null,
        is_terminal: progressionForm.is_terminal,
      });
      showSuccess("Class progression updated.");
      await loadClasses();
    } catch (err) {
      showError(getErrorMessage(err, "Could not update class progression."));
    } finally {
      setSaving("");
    }
  };

  const clearClassProgression = async () => {
    if (!progressionForm.class_id) {
      showWarning("Select a class before clearing progression.");
      return;
    }

    setSaving("progression-clear");
    try {
      await classService.clearClassProgression(progressionForm.class_id);
      showSuccess("Class progression cleared.");
      setProgressionForm((current) => ({
        ...current,
        next_class_id: "",
        is_terminal: false,
      }));
      await loadClasses();
    } catch (err) {
      showError(getErrorMessage(err, "Could not clear class progression."));
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
      await loadClasses();
    } catch (err) {
      showError(getErrorMessage(err, `Could not ${action} class.`));
    } finally {
      setSaving("");
      setPendingClassConfirmation(null);
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
      if (action === "delete") await academicService.deleteClassSubject(item.id);
      showSuccess(`Subject in class ${action}d.`);
      await loadClassSubjects();
    } catch (err) {
      showError(formatMappingError(err, `Could not ${action} this subject for the class.`));
    } finally {
      setSaving("");
      setPendingMappingConfirmation(null);
    }
  };

  const saveMappingEdit = async () => {
    if (!editingMapping) return;
    setSaving(editingMapping.id);
    try {
      await academicService.updateClassSubject(editingMapping.id, {
        is_core: editingMapping.is_core,
      });
      showSuccess("Subject settings updated for this class.");
      setEditingMapping(null);
      await loadClassSubjects();
    } catch (err) {
      showError(formatMappingError(err, "Could not update this subject for the class."));
    } finally {
      setSaving("");
    }
  };

  const openClassSubjectReview = async (item) => {
    setReviewingClass(item);
    setActiveSelectedClassId(item.id);
    setReviewClassSubjects([]);
    setReviewClassLoading(true);
    try {
      const response = await academicService.listOfferedClassSubjects(item.id, {
        active_only: false,
        include_archived: true,
        limit: 100,
      });
      setReviewClassSubjects(asItems(response));
    } catch (err) {
      showError(formatMappingError(err, "Could not load subjects for this class."));
    } finally {
      setReviewClassLoading(false);
    }
  };

  const classConfirmationDialog = (
    <TypedConfirmationDialog
      open={Boolean(pendingClassConfirmation)}
      title={pendingClassConfirmation?.title}
      description={pendingClassConfirmation?.description}
      confirmationText={pendingClassConfirmation?.confirmationText || ""}
      confirmLabel={pendingClassConfirmation?.confirmLabel}
      variant={pendingClassConfirmation?.variant}
      isLoading={saving === pendingClassConfirmation?.item?.id}
      onConfirm={() => {
        if (!pendingClassConfirmation) return;
        updateClassLifecycle(
          pendingClassConfirmation.item,
          pendingClassConfirmation.action,
        );
      }}
      onCancel={() => setPendingClassConfirmation(null)}
    />
  );

  const classViewDialog = (
    <Modal
      open={Boolean(viewingClass)}
      title={viewingClass ? classLabel(viewingClass) : "Class"}
      description="Class details"
      onClose={() => setViewingClass(null)}
      footer={
        <div className="flex justify-end">
          <Button type="button" variant="outline" onClick={() => setViewingClass(null)}>
            Close
          </Button>
        </div>
      }
    >
      {viewingClass ? (
        <div className="space-y-3 text-sm">
          <p>
            <span className="font-semibold text-text">Status:</span>{" "}
            {viewingClass.archived_at ? "archived" : viewingClass.is_active ? "active" : "inactive"}
          </p>
          <p>
            <span className="font-semibold text-text">Class teacher / homeroom teacher:</span>{" "}
            {viewingClass.teacher_membership_id
              ? teacherLabel(teachers.find((teacher) => teacher.id === viewingClass.teacher_membership_id))
              : "No class teacher / homeroom teacher"}
          </p>
          <p>
            <span className="font-semibold text-text">Progression:</span>{" "}
            {viewingClass.is_terminal
              ? "Terminal class"
              : viewingClass.next_class_id
                ? `Progresses to ${classLabel(classes.find((entry) => entry.id === viewingClass.next_class_id))}`
                : "Progression target not configured"}
          </p>
        </div>
      ) : null}
    </Modal>
  );

  const withClassConfirmationDialog = (view) => (
    <>
      {view}
      {classConfirmationDialog}
      {classViewDialog}
    </>
  );

  const classSearchControl = (
    <Input
      label="Search classes"
      value={classSearchDraft}
      onChange={(event) => setClassSearchDraft(event.target.value)}
      placeholder="Class name or arm"
    />
  );

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
              label="Class teacher / homeroom teacher"
              value={classForm.teacher_membership_id}
              onChange={(value) =>
                setClassForm((current) => ({
                  ...current,
                  teacher_membership_id: value,
                }))
              }
              options={teacherOptions}
              placeholder="Optional class teacher / homeroom teacher"
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
          listClassName="max-h-[32rem] overflow-y-auto overscroll-contain pr-1"
          renderTitle={classLabel}
          renderMeta={(item) =>
            item.teacher_membership_id
              ? teacherLabel(teachers.find((teacher) => teacher.id === item.teacher_membership_id))
              : "No class teacher / homeroom teacher"
          }
          renderDescription={(item) =>
            item.is_terminal
              ? "Terminal class"
              : item.next_class_id
                ? `Progresses to ${classLabel(classes.find((entry) => entry.id === item.next_class_id))}`
                : "Progression target not configured"
          }
          renderStatus={(item) => (item.archived_at ? "archived" : item.is_active ? "active" : "inactive")}
          actions={classSearchControl}
          renderActions={(item) => (
            <>
              {item.archived_at ? (
                <>
                  <Button
                    type="button"
                    size="small"
                    variant="outline"
                    onClick={() => setViewingClass(item)}
                  >
                    View
                  </Button>
                  <Button
                    type="button"
                    size="small"
                    variant="outline"
                    disabled={saving === item.id}
                    onClick={() =>
                      setPendingClassConfirmation(
                        classLifecycleConfirmation(item, "restore"),
                      )
                    }
                  >
                    Restore
                  </Button>
                </>
              ) : item.is_active ? (
                <Button
                  type="button"
                  size="small"
                  variant="outline"
                  disabled={saving === item.id}
                  onClick={() =>
                    setPendingClassConfirmation(
                      classLifecycleConfirmation(item, "deactivate"),
                    )
                  }
                >
                  Deactivate
                </Button>
              ) : (
                <>
                  <Button
                    type="button"
                    size="small"
                    variant="success"
                    disabled={saving === item.id}
                    onClick={() =>
                      setPendingClassConfirmation(
                        classLifecycleConfirmation(item, "activate"),
                      )
                    }
                  >
                    Activate
                  </Button>
                  <Button
                    type="button"
                    size="small"
                    variant="danger"
                    disabled={saving === item.id}
                    onClick={() =>
                      setPendingClassConfirmation(
                        classLifecycleConfirmation(item, "archive"),
                      )
                    }
                  >
                    Archive
                  </Button>
                </>
              )}
            </>
          )}
          canEdit={(item) => !item.archived_at}
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
          label="Class teacher / homeroom teacher"
          value={classForm.teacher_membership_id}
          onChange={(value) =>
            setClassForm((current) => ({
              ...current,
              teacher_membership_id: value,
            }))
          }
          options={teacherOptions}
          placeholder="Optional class teacher / homeroom teacher"
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
      listClassName="max-h-[32rem] overflow-y-auto overscroll-contain pr-1"
      renderTitle={classLabel}
      renderMeta={(item) =>
        item.teacher_membership_id
          ? teacherLabel(teachers.find((teacher) => teacher.id === item.teacher_membership_id))
          : "No class teacher / homeroom teacher"
      }
      renderDescription={(item) =>
        item.is_terminal
          ? "Terminal class"
          : item.next_class_id
            ? `Progresses to ${classLabel(classes.find((entry) => entry.id === item.next_class_id))}`
            : "Progression target not configured"
      }
      renderStatus={(item) => (item.archived_at ? "archived" : item.is_active ? "active" : "inactive")}
      actions={classSearchControl}
      renderActions={(item) => (
        <>
          {item.archived_at ? (
            <>
              <Button
                type="button"
                size="small"
                variant="outline"
                onClick={() => setViewingClass(item)}
              >
                View
              </Button>
              <Button
                type="button"
                size="small"
                variant="outline"
                disabled={saving === item.id}
                onClick={() =>
                  setPendingClassConfirmation(
                    classLifecycleConfirmation(item, "restore"),
                  )
                }
              >
                Restore
              </Button>
            </>
          ) : item.is_active ? (
            <Button
              type="button"
              size="small"
              variant="outline"
              disabled={saving === item.id}
              onClick={() =>
                setPendingClassConfirmation(
                  classLifecycleConfirmation(item, "deactivate"),
                )
              }
            >
              Deactivate
            </Button>
          ) : (
            <>
              <Button
                type="button"
                size="small"
                variant="success"
                disabled={saving === item.id}
                onClick={() =>
                  setPendingClassConfirmation(
                    classLifecycleConfirmation(item, "activate"),
                  )
                }
              >
                Activate
              </Button>
              <Button
                type="button"
                size="small"
                variant="danger"
                disabled={saving === item.id}
                onClick={() =>
                  setPendingClassConfirmation(
                    classLifecycleConfirmation(item, "archive"),
                  )
                }
              >
                Archive
              </Button>
            </>
          )}
        </>
      )}
      canEdit={(item) => !item.archived_at}
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

  const progressionView = (
    <WorkspaceGrid
      editor={
        <WorkspacePanel
          title="Configure progression"
          description="Choose where students move when this class is promoted, or mark the class as terminal."
        >
          <form className="space-y-3" onSubmit={saveClassProgression}>
            <SelectControl
              label="Class"
              value={progressionForm.class_id}
              onChange={setProgressionSourceClass}
              options={activeClassOptions}
              placeholder="Select source class"
              disabled={activeClassOptions.length === 0}
              required
            />
            <SelectControl
              label="Next class"
              value={progressionForm.next_class_id}
              onChange={(value) =>
                setProgressionForm((current) => ({
                  ...current,
                  next_class_id: value,
                  is_terminal: value ? false : current.is_terminal,
                }))
              }
              options={progressionTargetOptions}
              placeholder={
                progressionForm.is_terminal
                  ? "Terminal classes do not need a next class"
                  : "Select progression target"
              }
              disabled={
                progressionForm.is_terminal ||
                !progressionForm.class_id ||
                progressionTargetOptions.length === 0
              }
            />
            <CheckboxControl
              label="Terminal class"
              checked={progressionForm.is_terminal}
              onChange={(value) =>
                setProgressionForm((current) => ({
                  ...current,
                  is_terminal: value,
                  next_class_id: value ? "" : current.next_class_id,
                }))
              }
              disabled={!progressionForm.class_id}
            />
            <FormActions
              submitting={saving === "progression"}
              submitLabel="Save progression"
              disabled={!progressionForm.class_id}
            />
            <Button
              type="button"
              variant="outline"
              disabled={!progressionForm.class_id || saving === "progression-clear"}
              onClick={clearClassProgression}
            >
              {saving === "progression-clear" ? "Clearing..." : "Clear progression"}
            </Button>
          </form>
        </WorkspacePanel>
      }
      content={
        <RecordList
          title="Class progression"
          description="Active class promotion targets used when an academic session is closed."
          items={classes.filter((item) => item.is_active && !item.archived_at)}
          emptyIcon={Library}
          emptyTitle="No active classes"
          emptyDescription="Create and activate classes before configuring progression."
          renderTitle={classLabel}
          renderMeta={(item) =>
            item.teacher_membership_id
              ? teacherLabel(teachers.find((teacher) => teacher.id === item.teacher_membership_id))
              : "No class teacher / homeroom teacher"
          }
          renderDescription={(item) =>
            item.is_terminal
              ? "Terminal class"
              : item.next_class_id
                ? `Progresses to ${classLabel(classes.find((entry) => entry.id === item.next_class_id))}`
                : "Progression target not configured"
          }
          renderStatus={(item) =>
            item.is_terminal ? "terminal" : item.next_class_id ? "configured" : "missing"
          }
          onEdit={(item) => setProgressionSourceClass(item.id)}
        />
      }
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
            <MultiSelect
              label="Subjects"
              name="subject_ids"
              value={subjectSelection.subject_ids}
              onChange={(event) =>
                setSubjectSelection((current) => ({
                  ...current,
                  subject_ids: event.target.value,
                }))
              }
              options={subjectOptions}
              placeholder={
                subjectOptions.length === 0
                  ? "All active subjects are attached"
                  : "Search and select subjects"
              }
              searchPlaceholder="Search subjects"
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
              disabled={
                saving === "offering" ||
                subjectOptions.length === 0 ||
                subjectSelection.subject_ids.length === 0
              }
            >
              {saving === "offering"
                ? "Attaching..."
                : subjectSelection.subject_ids.length > 0
                  ? `Attach ${subjectSelection.subject_ids.length} subject${subjectSelection.subject_ids.length === 1 ? "" : "s"}`
                  : "Attach subjects"}
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
          {filteredClassSubjects.length === 0 ? (
            <p className="rounded-2xl border border-dashed border-border p-5 text-sm text-text-muted">
              {mappingEmptyMessage}
            </p>
          ) : (
            <div className="max-h-[calc(100vh-18rem)] overflow-y-auto pr-2">
              <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">
                {filteredClassSubjects.map((item) => (
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
                      <>
                        <Button
                          type="button"
                          size="small"
                          variant="outline"
                          disabled={saving === item.id}
                          onClick={() => setViewingMapping(item)}
                        >
                          View
                        </Button>
                        <Button
                          type="button"
                          size="small"
                          variant="outline"
                          disabled={saving === item.id}
                          onClick={() =>
                            setPendingMappingConfirmation(mappingLifecycleConfirmation(item, "restore"))
                          }
                        >
                          Restore
                        </Button>
                      </>
                    ) : item.is_active ? (
                      <>
                        <Button
                          type="button"
                          size="small"
                          variant="outline"
                          disabled={saving === item.id}
                          onClick={() => setEditingMapping({ ...item })}
                        >
                          Edit
                        </Button>
                        <Button
                          type="button"
                          size="small"
                          variant="outline"
                          disabled={saving === item.id}
                          onClick={() =>
                            setPendingMappingConfirmation(mappingLifecycleConfirmation(item, "deactivate"))
                          }
                        >
                          {saving === item.id ? "Working..." : "Deactivate"}
                        </Button>
                      </>
                    ) : (
                      <>
                        <Button
                          type="button"
                          size="small"
                          variant="outline"
                          disabled={saving === item.id}
                          onClick={() => setEditingMapping({ ...item })}
                        >
                          Edit
                        </Button>
                        <Button
                          type="button"
                          size="small"
                          variant="success"
                          disabled={saving === item.id}
                          onClick={() =>
                            setPendingMappingConfirmation(mappingLifecycleConfirmation(item, "activate"))
                          }
                        >
                          Activate
                        </Button>
                        <Button
                          type="button"
                          size="small"
                          variant="danger"
                          disabled={saving === item.id}
                          onClick={() =>
                            setPendingMappingConfirmation(mappingLifecycleConfirmation(item, "archive"))
                          }
                        >
                          Archive
                        </Button>
                        <Button
                          type="button"
                          size="small"
                          variant="danger"
                          disabled={saving === item.id}
                          onClick={() =>
                            setPendingMappingConfirmation(mappingLifecycleConfirmation(item, "delete"))
                          }
                        >
                          Delete
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              ))}
              </div>
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
      <Modal
        open={Boolean(editingMapping)}
        title="Edit subject in class"
        description={editingMapping?.subject_name || "Subject in class"}
        onClose={() => setEditingMapping(null)}
        footer={
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button
              type="button"
              variant="outline"
              onClick={() => setEditingMapping(null)}
              disabled={saving === editingMapping?.id}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={saveMappingEdit}
              disabled={saving === editingMapping?.id}
            >
              {saving === editingMapping?.id ? "Saving..." : "Save"}
            </Button>
          </div>
        }
      >
        {editingMapping ? (
          <CheckboxControl
            label="Core subject"
            checked={editingMapping.is_core}
            onChange={(value) =>
              setEditingMapping((current) => ({ ...current, is_core: value }))
            }
          />
        ) : null}
      </Modal>
      <Modal
        open={Boolean(viewingMapping)}
        title={viewingMapping?.subject_name || "Subject in class"}
        description="Archived class subject"
        onClose={() => setViewingMapping(null)}
        footer={
          <div className="flex justify-end">
            <Button type="button" variant="outline" onClick={() => setViewingMapping(null)}>
              Close
            </Button>
          </div>
        }
      >
        {viewingMapping ? (
          <div className="space-y-2 text-sm text-text-muted">
            <p>Status: {viewingMapping.lifecycle_status || "archived"}</p>
            <p>{viewingMapping.is_core ? "Core subject" : "Elective subject"}</p>
            {viewingMapping.activation_blocker ? <p>{viewingMapping.activation_blocker}</p> : null}
          </div>
        ) : null}
      </Modal>
    </>
  );

  const reviewView = (
    <WorkspacePanel
      title="Subjects taught in this class"
      description="Select a class to review the subjects currently attached to it."
    >
      <div className="max-h-[calc(100vh-15rem)] space-y-3 overflow-y-auto pr-2">
        {classes.length === 0 ? (
          <p className="rounded-2xl border border-dashed border-border p-5 text-sm text-text-muted">
            No classes are available for review.
          </p>
        ) : (
          classes.map((item) => {
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => openClassSubjectReview(item)}
                className="w-full rounded-2xl border border-border/70 bg-surface px-4 py-4 text-left transition hover:border-primary/30 hover:bg-primary-subtle/20"
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="font-semibold text-text">{classLabel(item)}</p>
                    <p className="mt-1 text-sm text-text-muted">
                      {item.teacher_membership_id
                        ? `Class teacher / homeroom teacher: ${teacherLabel(
                            teachers.find(
                              (teacher) => teacher.id === item.teacher_membership_id,
                            ),
                          )}`
                        : "No class teacher / homeroom teacher assigned"}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Badge variant={item.is_active ? "success" : "error"}>
                    {item.is_active ? "active" : "inactive"}
                  </Badge>
                  {item.is_terminal ? <Badge variant="warning">terminal</Badge> : null}
                </div>
              </div>
            </button>
            );
          })
        )}
      </div>
      <Modal
        open={Boolean(reviewingClass)}
        title={reviewingClass ? `${classLabel(reviewingClass)} subjects` : "Class subjects"}
        description="Subjects attached to this class"
        onClose={() => setReviewingClass(null)}
        footer={
          <div className="flex justify-end">
            <Button type="button" variant="outline" onClick={() => setReviewingClass(null)}>
              Close
            </Button>
          </div>
        }
      >
        <div className="max-h-[60vh] overflow-y-auto pr-2">
          {reviewClassLoading ? (
            <p className="rounded-2xl border border-dashed border-border p-5 text-sm text-text-muted">
              Loading subjects...
            </p>
          ) : reviewClassSubjects.length === 0 ? (
            <p className="rounded-2xl border border-dashed border-border p-5 text-sm text-text-muted">
              No subjects are attached to this class.
            </p>
          ) : (
            <div className="space-y-3">
              {reviewClassSubjects.map((item) => {
                const status = item.archived_at
                  ? "archived"
                  : item.is_active
                    ? "active"
                    : "inactive";
                return (
                  <div
                    key={item.id}
                    className="rounded-2xl border border-border/70 bg-surface px-4 py-3"
                  >
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <p className="break-words font-semibold text-text">
                          {item.subject_name || "Subject"}
                        </p>
                        <p className="mt-1 text-xs text-text-muted">
                          {item.subject_code || "No code"}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Badge variant={status === "active" ? "success" : status === "archived" ? "warning" : "error"}>
                          {status}
                        </Badge>
                        <Badge variant={item.is_core ? "primary" : "default"}>
                          {item.is_core ? "core" : "elective"}
                        </Badge>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </Modal>
    </WorkspacePanel>
  );

  if (error && !loading) {
    return (
      <WorkspacePanel title="Class structure unavailable">
        <p className="text-sm text-error">{error}</p>
        <Button type="button" className="mt-4" onClick={loadClasses}>
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
  if (activeTab === "progression") return progressionView;
  if (activeTab === "offerings") return offeringsView;
  if (activeTab === "review") return reviewView;
  if (editingClassId) return withClassConfirmationDialog(classesView);
  return withClassConfirmationDialog(classListView);
}

export default ClassStructureWorkspace;
