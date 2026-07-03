import { useCallback, useEffect, useMemo, useState } from "react";
import { Bell, CheckCircle2, Megaphone, Pin, Plus, Send, Trash2 } from "lucide-react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import { announcementService } from "../../services/announcementService";
import { classService } from "../../services/academicsService";
import { parentService } from "../../services/parentService";
import { studentService } from "../../services/studentService";
import { teacherService } from "../../services/teacherService";
import { getErrorMessage } from "../../services/api";
import { useToast } from "../../hooks/useToast";

const categories = [
  "general",
  "academic",
  "examination",
  "assignment",
  "attendance",
  "event",
  "holiday",
  "finance",
  "discipline",
  "sports",
  "club_activity",
  "health",
  "transport",
  "emergency",
  "system",
];

const priorities = ["low", "normal", "high", "urgent"];

const adminTargets = [
  { value: "all", label: "Everyone" },
  { value: "role", label: "Role" },
  { value: "class", label: "Class" },
  { value: "specific_student", label: "Specific student" },
  { value: "specific_parent", label: "Specific parent" },
  { value: "parents_of_student", label: "Parents of student" },
  { value: "parents_of_class", label: "Parents of class" },
];

const teacherTargets = [
  { value: "class", label: "Class" },
  { value: "specific_student", label: "Specific student" },
  { value: "parents_of_student", label: "Parents of student" },
  { value: "parents_of_class", label: "Parents of class" },
];

const roleOptions = [
  { value: "teacher", label: "Teachers" },
  { value: "parent", label: "Parents" },
  { value: "student", label: "Students" },
];

const emptyForm = {
  title: "",
  body: "",
  category: "general",
  priority: "normal",
  targetType: "all",
  role: "teacher",
  classId: "",
  studentId: "",
  parentId: "",
  teacherId: "",
  isPinned: false,
};

const normalizeItems = (response) => (Array.isArray(response) ? response : response?.items || []);

const displayName = (item, fallback = "Untitled") => {
  const name = [item?.first_name, item?.last_name].filter(Boolean).join(" ").trim();
  return name || item?.name || item?.title || item?.email || item?.admission_number || fallback;
};

const className = (item) => [item?.name, item?.arm].filter(Boolean).join(" ").trim() || "Class";

function buildTarget(form) {
  const target = { target_type: form.targetType };

  if (form.targetType === "role") target.role = form.role;
  if (["class", "parents_of_class"].includes(form.targetType)) target.class_id = form.classId;
  if (["specific_student", "parents_of_student"].includes(form.targetType)) target.student_id = form.studentId;
  if (form.targetType === "specific_parent") target.parent_id = form.parentId;
  if (form.targetType === "specific_teacher") target.teacher_id = form.teacherId;

  return target;
}

function isTeacherDirectMessage(item) {
  return Array.isArray(item?.targets) && item.targets.some((target) => target.target_type === "specific_teacher");
}

function resolveTeacherTarget(item, teachers) {
  const teacherId = item?.targets?.find((target) => target.target_type === "specific_teacher")?.teacher_id;
  if (!teacherId) return "Teacher not found";
  const teacher = teachers.find((entry) => entry.id === teacherId);
  return displayName(teacher, "Teacher");
}

function validateForm(form, mode, variant = "notices") {
  if (!form.title.trim()) return "Title is required.";
  if (!form.body.trim()) return "Message is required.";
  if (mode === "superadmin") return null;
  if (variant === "messages" && !form.teacherId) return "Choose a teacher.";
  if (form.targetType === "role" && !form.role) return "Choose a role.";
  if (["class", "parents_of_class"].includes(form.targetType) && !form.classId) return "Choose a class.";
  if (["specific_student", "parents_of_student"].includes(form.targetType) && !form.studentId) return "Choose a student.";
  if (form.targetType === "specific_parent" && !form.parentId) return "Choose a parent.";
  if (form.targetType === "specific_teacher" && !form.teacherId) return "Choose a teacher.";
  return null;
}

function SelectField({ label, value, onChange, children, disabled = false }) {
  return (
    <label className="block text-sm font-medium text-text-soft">
      <span className="mb-1.5 block">{label}</span>
      <select
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className="input-base"
      >
        {children}
      </select>
    </label>
  );
}

function AnnouncementForm({ mode, variant = "notices", options, onSubmit, isSubmitting }) {
  const isMessageComposer = variant === "messages";
  const [form, setForm] = useState({
    ...emptyForm,
    targetType: isMessageComposer ? "specific_teacher" : mode === "teacher" ? "class" : "all",
  });
  const { showWarning } = useToast();
  const targetOptions = mode === "teacher" ? teacherTargets : adminTargets;
  const isSuperadmin = mode === "superadmin";

  const update = (key, value) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const submit = async (event) => {
    event.preventDefault();
    const message = validateForm(form, mode, variant);
    if (message) {
      showWarning(message);
      return;
    }

    const payload = {
      title: form.title.trim(),
      body: form.body.trim(),
      category: form.category,
      priority: form.priority,
      is_pinned: form.isPinned,
      targets: isSuperadmin
        ? [{ target_type: "all" }]
        : isMessageComposer
          ? [{ target_type: "specific_teacher", teacher_id: form.teacherId }]
          : [buildTarget(form)],
    };

    await onSubmit(payload);
    setForm({
      ...emptyForm,
      targetType: isMessageComposer ? "specific_teacher" : mode === "teacher" ? "class" : "all",
    });
  };

  return (
    <form onSubmit={submit} className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
      <div className="grid gap-4 lg:grid-cols-2">
        <Input label="Title" value={form.title} onChange={(event) => update("title", event.target.value)} />
        <div className="grid gap-4 sm:grid-cols-2">
          <SelectField label="Category" value={form.category} onChange={(value) => update("category", value)}>
            {categories.map((category) => (
              <option key={category} value={category}>{category.replaceAll("_", " ")}</option>
            ))}
          </SelectField>
          <SelectField label="Priority" value={form.priority} onChange={(value) => update("priority", value)}>
            {priorities.map((priority) => (
              <option key={priority} value={priority}>{priority}</option>
            ))}
          </SelectField>
        </div>
      </div>

      <label className="mt-4 block text-sm font-medium text-text-soft">
        <span className="mb-1.5 block">Message</span>
        <textarea
          value={form.body}
          onChange={(event) => update("body", event.target.value)}
          className="input-base min-h-28 resize-y"
        />
      </label>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        {!isMessageComposer && (
          <SelectField
            label="Audience"
            value={isSuperadmin ? "tenant_admins" : form.targetType}
            disabled={isSuperadmin}
            onChange={(value) => update("targetType", value)}
          >
            {isSuperadmin ? (
              <option value="tenant_admins">Tenant admins only</option>
            ) : (
              targetOptions.map((target) => (
                <option key={target.value} value={target.value}>{target.label}</option>
              ))
            )}
          </SelectField>
        )}

        {isMessageComposer && (
          <SelectField label="Teacher" value={form.teacherId} onChange={(value) => update("teacherId", value)}>
            <option value="">Select teacher</option>
            {options.teachers.map((item) => (
              <option key={item.id} value={item.id}>{displayName(item, item.email)}</option>
            ))}
          </SelectField>
        )}

        {!isSuperadmin && form.targetType === "role" && (
          <SelectField label="Role" value={form.role} onChange={(value) => update("role", value)}>
            {roleOptions.map((role) => (
              <option key={role.value} value={role.value}>{role.label}</option>
            ))}
          </SelectField>
        )}

        {!isSuperadmin && ["class", "parents_of_class"].includes(form.targetType) && (
          <SelectField label="Class" value={form.classId} onChange={(value) => update("classId", value)}>
            <option value="">Select class</option>
            {options.classes.map((item) => (
              <option key={item.id} value={item.id}>{className(item)}</option>
            ))}
          </SelectField>
        )}

        {!isSuperadmin && ["specific_student", "parents_of_student"].includes(form.targetType) && (
          <SelectField label="Student" value={form.studentId} onChange={(value) => update("studentId", value)}>
            <option value="">Select student</option>
            {options.students.map((item) => (
              <option key={item.id} value={item.id}>{displayName(item, item.admission_number)}</option>
            ))}
          </SelectField>
        )}

        {!isSuperadmin && form.targetType === "specific_parent" && (
          <SelectField label="Parent" value={form.parentId} onChange={(value) => update("parentId", value)}>
            <option value="">Select parent</option>
            {options.parents.map((item) => (
              <option key={item.id} value={item.id}>{displayName(item, item.email)}</option>
            ))}
          </SelectField>
        )}

        {!isMessageComposer && !isSuperadmin && form.targetType === "specific_teacher" && (
          <SelectField label="Teacher" value={form.teacherId} onChange={(value) => update("teacherId", value)}>
            <option value="">Select teacher</option>
            {options.teachers.map((item) => (
              <option key={item.id} value={item.id}>{displayName(item, item.email)}</option>
            ))}
          </SelectField>
        )}
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        {!isMessageComposer && (
          <label className="inline-flex items-center gap-2 text-sm font-medium text-text-soft">
            <input
              type="checkbox"
              checked={form.isPinned}
              onChange={(event) => update("isPinned", event.target.checked)}
              className="h-4 w-4 rounded border-border"
            />
            Pin announcement
          </label>
        )}
        <Button type="submit" disabled={isSubmitting}>
          {isMessageComposer ? <Send className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
          {isMessageComposer ? "Send message" : "Create"}
        </Button>
      </div>
    </form>
  );
}

function AnnouncementList({ items, mode, variant = "notices", options, onPublish, onArchive, onDelete }) {
  if (!items.length) {
    return (
      <EmptyState
        icon={Megaphone}
        title={variant === "messages" ? "No messages yet" : "No announcements yet"}
        description={
          variant === "messages"
            ? "Send a direct message to a teacher and publish it when it is ready."
            : "Create an announcement and publish it when it is ready."
        }
      />
    );
  }

  return (
    <div className="grid gap-3">
      {items.map((item) => (
        <article key={item.id} className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-base font-semibold text-text">{item.title}</h3>
                {item.is_pinned && <Pin className="h-4 w-4 text-primary" />}
                <span className="rounded-full bg-surface-muted px-2.5 py-1 text-xs font-semibold capitalize text-text-soft">
                  {item.status}
                </span>
                <span className="rounded-full bg-primary-soft px-2.5 py-1 text-xs font-semibold capitalize text-primary">
                  {String(item.category || "general").replaceAll("_", " ")}
                </span>
              </div>
              {variant === "messages" && (
                <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-text-muted">
                  Teacher: {resolveTeacherTarget(item, options.teachers)}
                </p>
              )}
              <p className="mt-2 whitespace-pre-line text-sm leading-6 text-text-soft">{item.body}</p>
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              {item.status !== "published" && (
                <Button type="button" size="sm" onClick={() => onPublish(item.id)}>
                  <Send className="h-4 w-4" />
                  Publish
                </Button>
              )}
              {item.status === "published" && (
                <Button type="button" size="sm" variant="outline" onClick={() => onArchive(item.id)}>
                  Archive
                </Button>
              )}
              {mode !== "feed" && (
                <Button type="button" size="sm" variant="danger" onClick={() => onDelete(item.id)}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}

function AnnouncementFeed({ items, onRead, onAcknowledge, variant = "notices" }) {
  if (!items.length) {
    return (
      <EmptyState
        icon={Bell}
        title={variant === "messages" ? "No messages yet" : "No notices yet"}
        description={
          variant === "messages"
            ? "Direct messages from your administrators will appear here."
            : "Published notices for you will appear here."
        }
      />
    );
  }

  return (
    <div className="grid gap-3">
      {items.map((item) => (
        <article key={item.id} className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-base font-semibold">{item.title}</h3>
                {!item.is_read && (
                  <span className="rounded-full bg-accent-soft px-2.5 py-1 text-xs font-semibold text-accent">Unread</span>
                )}
                {item.is_acknowledged && (
                  <span className="rounded-full bg-success-soft px-2.5 py-1 text-xs font-semibold text-success">Acknowledged</span>
                )}
              </div>
              <p className="mt-2 whitespace-pre-line text-sm leading-6 text-text-soft">{item.body}</p>
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              {!item.is_read && (
                <Button type="button" size="sm" variant="outline" onClick={() => onRead(item.id)}>
                  <CheckCircle2 className="h-4 w-4" />
                  Mark read
                </Button>
              )}
              {!item.is_acknowledged && (
                <Button type="button" size="sm" onClick={() => onAcknowledge(item.id)}>
                  Acknowledge
                </Button>
              )}
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}

function AnnouncementsWorkspacePage({ mode, variant = "notices" }) {
  const role = mode === "tenant-admin" ? "admin" : mode;
  const isMessages = variant === "messages";
  const isReceivedNotices = variant === "received-notices";
  const isFeed =
    mode === "parent" ||
    mode === "student" ||
    (mode === "teacher" && isReceivedNotices);
  const [items, setItems] = useState([]);
  const [options, setOptions] = useState({ classes: [], students: [], parents: [], teachers: [] });
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const { showSuccess, showError } = useToast();

  const copy = useMemo(() => {
    if (mode === "superadmin") {
      return {
        title: "Platform Announcements",
        description: "Create platform notices for tenant administrators.",
      };
    }
    if (mode === "tenant-admin" && isMessages) {
      return {
        title: "Messages",
        description: "Send direct messages to individual teachers without mixing them into school-wide notices.",
      };
    }
    if (mode === "teacher" && isReceivedNotices) {
      return {
        title: "Notices",
        description: "Read general school notices that were sent to teachers.",
      };
    }
    if (mode === "teacher") {
      return {
        title: "Class Notices",
        description: "Create notices for your assigned classes, students, and their parents.",
      };
    }
    if (isFeed) {
      return {
        title: "Notices",
        description: "Read and acknowledge announcements sent to you.",
      };
    }
    return {
      title: "Notices & Announcements",
      description: "Create and publish school announcements for staff, parents, and students.",
    };
  }, [isFeed, isMessages, isReceivedNotices, mode]);

  const listAnnouncements = useCallback(async () => {
    if (mode === "superadmin") return announcementService.listSuperadminAnnouncements();
    if (mode === "teacher" && isReceivedNotices) return announcementService.getFeed({ delivery_kind: "notice" });
    if (mode === "teacher") return announcementService.listTeacherAnnouncements();
    if (mode === "tenant-admin") return announcementService.listTenantAdminAnnouncements();
    return announcementService.getFeed();
  }, [isReceivedNotices, mode]);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const [announcementResponse, classes, students, parents, teachers] = await Promise.all([
        listAnnouncements(),
        isFeed ? Promise.resolve({ items: [] }) : classService.getClasses({ limit: 100 }),
        mode === "superadmin" || isFeed
          ? Promise.resolve({ items: [] })
          : mode === "teacher"
            ? studentService.getStudents({ limit: 100 })
            : studentService.getAdminStudents({ limit: 100 }),
        mode === "tenant-admin" ? parentService.getParents({ limit: 100 }) : Promise.resolve({ items: [] }),
        mode === "tenant-admin" ? teacherService.getTeachers({ limit: 100 }) : Promise.resolve({ items: [] }),
      ]);

      let announcementItems = normalizeItems(announcementResponse);
      if (mode === "tenant-admin" && isMessages) {
        announcementItems = announcementItems.filter(isTeacherDirectMessage);
      } else if (mode === "tenant-admin") {
        announcementItems = announcementItems.filter((item) => !isTeacherDirectMessage(item));
      }

      setItems(announcementItems);
      setOptions({
        classes: normalizeItems(classes),
        students: normalizeItems(students),
        parents: normalizeItems(parents),
        teachers: normalizeItems(teachers),
      });
    } catch (loadError) {
      setError(getErrorMessage(loadError, "Unable to load announcements."));
    } finally {
      setIsLoading(false);
    }
  }, [isFeed, isMessages, listAnnouncements, mode]);

  useEffect(() => {
    const timeoutId = window.setTimeout(load, 0);
    return () => window.clearTimeout(timeoutId);
  }, [load]);

  const createAnnouncement = async (payload) => {
    setIsSubmitting(true);
    try {
      if (mode === "superadmin") await announcementService.createSuperadminAnnouncement(payload);
      if (mode === "teacher") await announcementService.createTeacherAnnouncement(payload);
      if (mode === "tenant-admin") await announcementService.createTenantAdminAnnouncement(payload);
      await load();
      showSuccess(isMessages ? "Message created successfully." : "Announcement created successfully.");
    } catch (submitError) {
      showError(getErrorMessage(submitError, "Unable to create announcement."));
    } finally {
      setIsSubmitting(false);
    }
  };

  const publish = async (id) => {
    try {
      if (mode === "superadmin") await announcementService.publishSuperadminAnnouncement(id);
      if (mode === "teacher") await announcementService.publishTeacherAnnouncement(id);
      if (mode === "tenant-admin") await announcementService.publishTenantAdminAnnouncement(id);
      await load();
      showSuccess(isMessages ? "Message published successfully." : "Announcement published successfully.");
    } catch (publishError) {
      showError(getErrorMessage(publishError, "Unable to publish announcement."));
    }
  };

  const archive = async (id) => {
    try {
      if (mode === "superadmin") await announcementService.archiveSuperadminAnnouncement(id);
      if (mode === "teacher") await announcementService.archiveTeacherAnnouncement(id);
      if (mode === "tenant-admin") await announcementService.archiveTenantAdminAnnouncement(id);
      await load();
      showSuccess("Announcement archived successfully.");
    } catch (archiveError) {
      showError(getErrorMessage(archiveError, "Unable to archive announcement."));
    }
  };

  const remove = async (id) => {
    try {
      if (mode === "superadmin") await announcementService.deleteSuperadminAnnouncement(id);
      if (mode === "teacher") await announcementService.deleteTeacherAnnouncement(id);
      if (mode === "tenant-admin") await announcementService.deleteTenantAdminAnnouncement(id);
      await load();
      showSuccess(isMessages ? "Message deleted successfully." : "Announcement deleted successfully.");
    } catch (deleteError) {
      showError(getErrorMessage(deleteError, "Unable to delete announcement."));
    }
  };

  const markRead = async (id) => {
    try {
      await announcementService.markRead(id);
      await load();
      showSuccess("Notice marked as read.");
    } catch (readError) {
      showError(getErrorMessage(readError, "Unable to mark notice as read."));
    }
  };

  const acknowledge = async (id) => {
    try {
      await announcementService.acknowledge(id);
      await load();
      showSuccess("Notice acknowledged.");
    } catch (acknowledgeError) {
      showError(getErrorMessage(acknowledgeError, "Unable to acknowledge notice."));
    }
  };

  return (
    <DashboardLayout role={role} title={copy.title} description={copy.description}>
      <div className="space-y-5">
        {error && (
          <div className="rounded-2xl border border-error/20 bg-error-soft px-4 py-3 text-sm font-medium text-error">
            {error}
          </div>
        )}

        {!isFeed && (
          <AnnouncementForm
            mode={mode === "tenant-admin" ? "admin" : mode}
            variant={variant}
            options={options}
            onSubmit={createAnnouncement}
            isSubmitting={isSubmitting}
          />
        )}

        {isLoading ? (
          <LoadingState label="Loading announcements" />
        ) : isFeed ? (
          <AnnouncementFeed items={items} onRead={markRead} onAcknowledge={acknowledge} variant={variant} />
        ) : (
          <AnnouncementList
            items={items}
            mode={mode}
            variant={variant}
            options={options}
            onPublish={publish}
            onArchive={archive}
            onDelete={remove}
          />
        )}
      </div>
    </DashboardLayout>
  );
}

export default AnnouncementsWorkspacePage;
