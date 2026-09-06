import { useCallback, useEffect, useMemo, useState } from "react";
import { Archive, Megaphone, Send, XCircle } from "lucide-react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import { classService } from "../../services/academicsService";
import { academicService } from "../../services/academicService";
import { getErrorMessage } from "../../services/api";
import {
  communicationNoticeService,
  messageService,
} from "../../services/communicationService";
import { superadminService } from "../../services/superadmin.service";

const adminAudiences = [
  ["all_teachers", "All teachers"],
  ["selected_teachers", "Selected teacher"],
  ["all_students", "All students"],
  ["selected_students", "Selected student"],
  ["class_students", "Students in a class"],
  ["all_parents", "All parents"],
  ["selected_parents", "Selected parent"],
  ["class_parents", "Parents of a class"],
];
const teacherAudiences = [
  ["class_students", "Students in an assigned class"],
  ["class_parents", "Parents of my class-teacher class"],
];
const superadminAudiences = [
  ["all_tenant_admins", "All active tenant admins"],
  ["selected_tenant_admins", "Selected tenant admin"],
  ["tenant_admins_of_tenants", "Tenant admins of a tenant"],
];
const selectedActorTypes = {
  selected_teachers: "teacher",
  selected_students: "student",
  selected_parents: "parent",
  selected_tenant_admins: "tenant_admin",
};
const PAGE_SIZE = 20;

const normalizeItems = (value) => (Array.isArray(value) ? value : value?.items || []);
const classLabel = (item) =>
  item?.display_name ||
  item?.class_name ||
  [item?.academic_level_name, item?.arm_label || item?.class_arm]
    .filter(Boolean)
    .join(" ") ||
  "Class";

function buildPayload(form) {
  const audience = { audience_type: form.audienceType };
  if (form.actorId) audience.actor_id = form.actorId;
  if (form.classId) audience.class_id = form.classId;
  if (form.tenantId) audience.tenant_target_id = form.tenantId;
  return {
    title: form.title.trim(),
    body: form.body.trim(),
    category: form.category,
    priority: form.priority,
    is_pinned: form.isPinned,
    audiences: [audience],
  };
}

export default function NoticeManagementPage({ mode = "tenant-admin" }) {
  const audienceOptions =
    mode === "superadmin"
      ? superadminAudiences
      : mode === "teacher"
        ? teacherAudiences
        : adminAudiences;
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [recipients, setRecipients] = useState([]);
  const [classes, setClasses] = useState([]);
  const [tenants, setTenants] = useState([]);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [formError, setFormError] = useState("");
  const [form, setForm] = useState({
    title: "",
    body: "",
    category: "general",
    priority: "normal",
    audienceType: audienceOptions[0][0],
    actorId: "",
    classId: "",
    tenantId: "",
    isPinned: false,
  });

  const actorType = selectedActorTypes[form.audienceType] || "";
  const actorOptions = useMemo(
    () => recipients.filter((item) => !actorType || item.actor_type === actorType),
    [actorType, recipients],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const requests = [
        communicationNoticeService.list(mode, {
          skip: (page - 1) * PAGE_SIZE,
          limit: PAGE_SIZE,
        }),
        messageService.availableRecipients(),
      ];
      if (mode === "superadmin") {
        requests.push(superadminService.getTenants(0, 100, false));
      } else {
        requests.push(classService.getClasses({ limit: 100, activeOnly: true }));
      }
      if (mode === "teacher") {
        requests.push(academicService.listMyTeacherAssignments());
      }
      const responses = await Promise.all(requests);
      setItems(responses[0]?.items || []);
      setTotal(Number(responses[0]?.total || responses[0]?.items?.length || 0));
      setRecipients(
        (responses[1]?.groups || []).flatMap((group) =>
          (group.recipients || []).map((item) => ({
            ...item,
            group_label: item.group_label || group.label,
          })),
        ),
      );
      if (mode === "superadmin") {
        setTenants(normalizeItems(responses[2]));
      } else {
        const classRows = normalizeItems(responses[2]);
        if (mode === "teacher") {
          const assignmentClasses = normalizeItems(responses[3]).map((item) => ({
            id: item.class_id,
            class_name: item.class_name,
            class_arm: item.class_arm,
          }));
          const merged = new Map();
          [...classRows, ...assignmentClasses].forEach((item) => {
            if (item?.id) merged.set(item.id, item);
          });
          setClasses([...merged.values()]);
        } else {
          setClasses(classRows);
        }
      }
    } catch (err) {
      setError(getErrorMessage(err, "Could not load notices."));
    } finally {
      setLoading(false);
    }
  }, [mode, page]);

  useEffect(() => {
    load();
  }, [load]);

  const update = (key, value) => {
    setForm((current) => ({ ...current, [key]: value }));
    setPreview(null);
  };

  const changeAudience = (audienceType) => {
    setForm((current) => ({
      ...current,
      audienceType,
      actorId: "",
      classId: "",
      tenantId: "",
    }));
    setPreview(null);
  };

  const previewRecipients = async () => {
    setFormError("");
    try {
      const response = await communicationNoticeService.preview(mode, buildPayload(form));
      setPreview(response);
    } catch (err) {
      setFormError(getErrorMessage(err, "Could not preview notice recipients."));
    }
  };

  const submit = async (event) => {
    event.preventDefault();
    setFormError("");
    if (!form.title.trim() || !form.body.trim()) {
      setFormError("Title and message are required.");
      return;
    }
    try {
      const payload = buildPayload(form);
      const recipientPreview = await communicationNoticeService.preview(mode, payload);
      setPreview(recipientPreview);
      if (!Number(recipientPreview?.recipient_count || 0)) {
        setFormError("No active recipients match this audience.");
        return;
      }
      const notice = await communicationNoticeService.create(mode, payload);
      await communicationNoticeService.publish(mode, notice.id, {});
      setForm((current) => ({ ...current, title: "", body: "" }));
      setPreview(null);
      setPage(1);
      await load();
    } catch (err) {
      setFormError(getErrorMessage(err, "Could not publish notice."));
    }
  };

  const mutate = async (action) => {
    try {
      await action();
      await load();
    } catch (err) {
      setError(getErrorMessage(err, "Could not update notice."));
    }
  };

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const needsActor = Boolean(actorType);
  const needsClass = ["class_students", "class_parents"].includes(form.audienceType);
  const needsTenant = form.audienceType === "tenant_admins_of_tenants";

  return (
    <DashboardLayout
      role={mode === "tenant-admin" ? "admin" : mode}
      title="Notices"
      description="One-way school notices delivered to a hierarchy-authorized audience."
    >
      <section className="grid w-full gap-4 sm:gap-5 xl:grid-cols-[26rem_1fr]">
        <form
          onSubmit={submit}
          className="space-y-4 rounded-2xl border border-border bg-surface p-4"
        >
          <Input
            label="Title"
            value={form.title}
            onChange={(event) => update("title", event.target.value)}
          />
          <label className="block text-sm font-semibold text-text-soft">
            <span className="mb-1.5 block">Message</span>
            <textarea
              className="input-base min-h-28 resize-y"
              value={form.body}
              onChange={(event) => update("body", event.target.value)}
            />
          </label>
          <label className="block text-sm font-semibold text-text-soft">
            <span className="mb-1.5 block">Audience</span>
            <select
              className="input-base"
              value={form.audienceType}
              onChange={(event) => changeAudience(event.target.value)}
            >
              {audienceOptions.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
          {needsActor ? (
            <label className="block text-sm font-semibold text-text-soft">
              <span className="mb-1.5 block">Recipient</span>
              <select
                className="input-base"
                value={form.actorId}
                onChange={(event) => update("actorId", event.target.value)}
              >
                <option value="">Choose recipient</option>
                {actorOptions.map((item) => (
                  <option key={`${item.actor_type}:${item.actor_id}`} value={item.actor_id}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          {needsClass ? (
            <label className="block text-sm font-semibold text-text-soft">
              <span className="mb-1.5 block">Class</span>
              <select
                className="input-base"
                value={form.classId}
                onChange={(event) => update("classId", event.target.value)}
              >
                <option value="">Choose class</option>
                {classes.map((item) => (
                  <option key={item.id} value={item.id}>{classLabel(item)}</option>
                ))}
              </select>
            </label>
          ) : null}
          {needsTenant ? (
            <label className="block text-sm font-semibold text-text-soft">
              <span className="mb-1.5 block">School</span>
              <select
                className="input-base"
                value={form.tenantId}
                onChange={(event) => update("tenantId", event.target.value)}
              >
                <option value="">Choose school</option>
                {tenants.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.school_name || item.name || item.email}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm font-semibold text-text-soft">
              <span className="mb-1.5 block">Category</span>
              <select
                className="input-base"
                value={form.category}
                onChange={(event) => update("category", event.target.value)}
              >
                {["general", "academic", "attendance", "event", "finance", "emergency", "system"].map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </label>
            <label className="block text-sm font-semibold text-text-soft">
              <span className="mb-1.5 block">Priority</span>
              <select
                className="input-base"
                value={form.priority}
                onChange={(event) => update("priority", event.target.value)}
              >
                {["low", "normal", "high", "urgent"].map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </label>
          </div>
          <label className="flex items-center gap-2 text-sm font-semibold text-text-soft">
            <input
              type="checkbox"
              checked={form.isPinned}
              onChange={(event) => update("isPinned", event.target.checked)}
            />
            Pin this notice
          </label>
          {preview ? (
            <div className="rounded-xl border border-border bg-surface-muted p-3 text-sm">
              <strong>{preview.recipient_count} recipient{preview.recipient_count === 1 ? "" : "s"}</strong>
              {preview.excluded_count ? (
                <p className="mt-1 text-text-muted">{preview.excluded_reasons?.join(" · ")}</p>
              ) : null}
            </div>
          ) : null}
          {formError ? <p className="text-sm font-semibold text-error">{formError}</p> : null}
          <div className="flex gap-2">
            <Button type="button" variant="outline" onClick={previewRecipients}>Preview</Button>
            <Button type="submit"><Send className="h-4 w-4" /> Publish notice</Button>
          </div>
        </form>

        <div className="space-y-4">
          {loading ? <LoadingState label="Loading notices" /> : null}
          {!loading && error ? (
            <div className="rounded-xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-semibold text-error">{error}</div>
          ) : null}
          {!loading && !error && !items.length ? (
            <EmptyState icon={Megaphone} title="No notices yet" />
          ) : null}
          {items.map((item) => (
            <article key={item.id} className="rounded-2xl border border-border bg-surface p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="font-bold text-text">{item.title}</h2>
                    <span className="rounded-full bg-surface-muted px-2 py-0.5 text-xs font-bold text-text-muted">{item.status}</span>
                  </div>
                  <p className="mt-2 whitespace-pre-wrap text-sm text-text-muted">{item.body}</p>
                </div>
                <div className="flex gap-2">
                  {item.status === "published" ? (
                    <Button size="sm" variant="outline" onClick={() => mutate(() => communicationNoticeService.archive(mode, item.id))}>
                      <Archive className="h-4 w-4" /> Archive
                    </Button>
                  ) : null}
                  {["draft", "scheduled"].includes(item.status) ? (
                    <Button size="sm" variant="ghost" onClick={() => mutate(() => communicationNoticeService.cancel(mode, item.id))}>
                      <XCircle className="h-4 w-4" /> Cancel
                    </Button>
                  ) : null}
                </div>
              </div>
            </article>
          ))}
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-semibold text-text-muted">Page {page} of {pageCount}</span>
            <div className="flex gap-2">
              <Button size="small" variant="outline" disabled={page <= 1 || loading} onClick={() => setPage((value) => Math.max(1, value - 1))}>Previous</Button>
              <Button size="small" variant="outline" disabled={page >= pageCount || loading} onClick={() => setPage((value) => Math.min(pageCount, value + 1))}>Next</Button>
            </div>
          </div>
        </div>
      </section>
    </DashboardLayout>
  );
}
