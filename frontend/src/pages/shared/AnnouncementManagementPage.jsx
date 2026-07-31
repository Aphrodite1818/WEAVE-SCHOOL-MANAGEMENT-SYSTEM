import { useCallback, useEffect, useMemo, useState } from "react";
import { Archive, Megaphone, Send, XCircle } from "lucide-react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import { getErrorMessage } from "../../services/api";
import { classService } from "../../services/academicsService";
import { messageService, communicationAnnouncementService } from "../../services/communicationService";
import { superadminService } from "../../services/superadmin.service";

const tenantAudiences = [
  { value: "all_teachers", label: "All teachers" },
  { value: "selected_teachers", label: "Selected teachers" },
  { value: "all_students", label: "All students" },
  { value: "selected_students", label: "Selected students" },
  { value: "class_students", label: "Students in a class" },
  { value: "all_parents", label: "All parents" },
  { value: "selected_parents", label: "Selected parents" },
  { value: "class_parents", label: "Parents of a class" },
];

const superadminAudiences = [
  { value: "all_tenant_admins", label: "All active tenant admins" },
  { value: "selected_tenant_admins", label: "Selected tenant admins" },
  { value: "tenant_admins_of_tenants", label: "Tenant admins of selected tenants" },
];

function buildPayload(form) {
  const selectedActorAudience = selectedActorTypeByAudience[form.audienceType];
  const audiences = selectedActorAudience
    ? form.actorIds.map((actorId) => ({
        audience_type: form.audienceType,
        actor_id: actorId,
      }))
    : [{ audience_type: form.audienceType }];

  if (!selectedActorAudience && form.classId) audiences[0].class_id = form.classId;
  if (!selectedActorAudience && form.tenantTargetId) audiences[0].tenant_target_id = form.tenantTargetId;

  return {
    title: form.title.trim(),
    body: form.body.trim(),
    category: form.category,
    priority: form.priority,
    audiences,
    is_pinned: form.isPinned,
  };
}

const normalizeItems = (response) => (Array.isArray(response) ? response : response?.items || []);

const classLabel = (item) => [item?.name, item?.arm].filter(Boolean).join(" ").trim() || "Class";

const flattenRecipientGroups = (groups) =>
  (groups || []).flatMap((group) =>
    (group.recipients || []).map((recipient) => ({
      ...recipient,
      group_label: recipient.group_label || group.label,
    })),
  );

const selectedActorTypeByAudience = {
  selected_teachers: "teacher",
  selected_students: "student",
  selected_parents: "parent",
  selected_tenant_admins: "tenant_admin",
};

const archivedPreferenceKey = (mode) => `weave:${mode}:show-archived-announcements`;
const ANNOUNCEMENT_PAGE_SIZE = 20;

function SearchableOptionPicker({
  label,
  placeholder,
  search,
  onSearch,
  value,
  onSelect,
  options,
  selectedOptions: selectedOptionsOverride,
  getOptionLabel,
  getOptionMeta,
  emptyLabel = "No matching options",
  multi = false,
}) {
  const selectedValues = Array.isArray(value) ? value : value ? [value] : [];
  const selectedOptions = selectedOptionsOverride || options.filter((item) => selectedValues.includes(item.id || item.actor_id));

  return (
    <div className="space-y-2">
      <Input
        label={label}
        value={search}
        onChange={(event) => onSearch(event.target.value)}
        placeholder={placeholder}
      />
      <div className="max-h-56 overflow-y-auto rounded-lg border border-border bg-surface shadow-sm">
        {options.length ? (
          options.map((item) => {
            const optionValue = item.id || item.actor_id;
            const isSelected = selectedValues.includes(optionValue);
            return (
              <button
                key={`${item.actor_type || "option"}:${optionValue}`}
                type="button"
                onClick={() => onSelect(optionValue)}
                className={`block w-full border-b border-border px-3 py-2 text-left last:border-b-0 ${isSelected ? "is-selected-highlight" : "hover:bg-surface-muted/60"}`}
              >
                <span className="flex items-center justify-between gap-3">
                  <span className="block truncate text-sm font-semibold">{getOptionLabel(item)}</span>
                  {multi && isSelected ? <span className="text-xs font-bold">Selected</span> : null}
                </span>
                {getOptionMeta ? (
                  <span className="mt-0.5 block truncate text-xs text-text-muted">{getOptionMeta(item)}</span>
                ) : null}
              </button>
            );
          })
        ) : (
          <p className="px-3 py-4 text-sm text-text-muted">{emptyLabel}</p>
        )}
      </div>
      {selectedOptions.length ? (
        <div className="flex flex-wrap gap-2">
          {selectedOptions.map((item) => {
            const optionValue = item.id || item.actor_id;
            return (
              <button
                key={`selected:${optionValue}`}
                type="button"
                onClick={() => onSelect(optionValue)}
                className="is-selected-highlight rounded-lg px-2.5 py-1 text-xs font-semibold"
              >
                {getOptionLabel(item)}
              </button>
            );
          })}
        </div>
      ) : null}
      {multi && selectedValues.length ? (
        <p className="text-xs font-semibold text-text-muted">
          {selectedValues.length} audience member{selectedValues.length === 1 ? "" : "s"} selected
        </p>
      ) : null}
    </div>
  );
}

export default function AnnouncementManagementPage({ mode = "tenant-admin" }) {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [showArchived, setShowArchived] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.localStorage.getItem(archivedPreferenceKey(mode)) === "true";
  });
  const [form, setForm] = useState({
    title: "",
    body: "",
    category: "general",
    priority: "normal",
    audienceType: mode === "superadmin" ? "all_tenant_admins" : "all_teachers",
    actorIds: [],
    classId: "",
    tenantTargetId: "",
    isPinned: false,
  });
  const [preview, setPreview] = useState(null);
  const [recipientGroups, setRecipientGroups] = useState([]);
  const [classes, setClasses] = useState([]);
  const [tenants, setTenants] = useState([]);
  const [recipientSearch, setRecipientSearch] = useState("");
  const [classSearch, setClassSearch] = useState("");
  const [tenantSearch, setTenantSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [formError, setFormError] = useState("");

  const audienceOptions = useMemo(() => (mode === "superadmin" ? superadminAudiences : tenantAudiences), [mode]);
  const recipients = useMemo(() => flattenRecipientGroups(recipientGroups), [recipientGroups]);
  const selectedActorType = selectedActorTypeByAudience[form.audienceType] || "";
  const selectedAudienceMembers = useMemo(
    () =>
      recipients.filter(
        (recipient) =>
          (!selectedActorType || recipient.actor_type === selectedActorType) &&
          form.actorIds.includes(recipient.actor_id),
      ),
    [form.actorIds, recipients, selectedActorType],
  );
  const filteredRecipients = useMemo(() => {
    const query = recipientSearch.trim().toLowerCase();
    return recipients
      .filter((recipient) => !selectedActorType || recipient.actor_type === selectedActorType)
      .filter((recipient) => !query || recipient.label.toLowerCase().includes(query))
      .slice(0, 25);
  }, [recipientSearch, recipients, selectedActorType]);
  const filteredClasses = useMemo(() => {
    const query = classSearch.trim().toLowerCase();
    return classes
      .filter((item) => !query || classLabel(item).toLowerCase().includes(query))
      .slice(0, 25);
  }, [classSearch, classes]);
  const filteredTenants = useMemo(() => {
    const query = tenantSearch.trim().toLowerCase();
    return tenants
      .filter((item) => !query || String(item.school_name || item.name || item.email || "").toLowerCase().includes(query))
      .slice(0, 25);
  }, [tenantSearch, tenants]);
  const visibleItems = useMemo(
    () => (showArchived ? items : items.filter((item) => item.status !== "archived")),
    [items, showArchived],
  );
  const archivedCount = items.filter((item) => item.status === "archived").length;
  const pageCount = Math.max(1, Math.ceil(total / ANNOUNCEMENT_PAGE_SIZE));

  useEffect(() => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(archivedPreferenceKey(mode), String(showArchived));
    }
  }, [mode, showArchived]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const skip = (page - 1) * ANNOUNCEMENT_PAGE_SIZE;
      const [response, recipientResponse, classResponse, tenantResponse] = await Promise.all([
        communicationAnnouncementService.list(mode, { skip, limit: ANNOUNCEMENT_PAGE_SIZE }),
        messageService.availableRecipients(),
        mode === "tenant-admin" ? classService.getClasses({ limit: 100, activeOnly: true }) : Promise.resolve({ items: [] }),
        mode === "superadmin" ? superadminService.getTenants(0, 100, false) : Promise.resolve({ items: [] }),
      ]);
      setItems(response?.items || []);
      setTotal(Number(response?.total || response?.items?.length || 0));
      setRecipientGroups(recipientResponse?.groups || []);
      setClasses(normalizeItems(classResponse));
      setTenants(normalizeItems(tenantResponse));
    } catch (err) {
      setError(getErrorMessage(err, "Could not load announcements."));
    } finally {
      setLoading(false);
    }
  }, [mode, page]);

  useEffect(() => {
    load();
  }, [load]);

  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));
  const updateAudience = (value) => {
    setForm((current) => ({
      ...current,
      audienceType: value,
      actorIds: [],
      classId: "",
      tenantTargetId: "",
    }));
    setPreview(null);
    setRecipientSearch("");
    setClassSearch("");
    setTenantSearch("");
  };

  const toggleAudienceActor = (actorId) => {
    setForm((current) => {
      const existing = new Set(current.actorIds);
      if (existing.has(actorId)) {
        existing.delete(actorId);
      } else {
        existing.add(actorId);
      }
      return { ...current, actorIds: [...existing] };
    });
    setPreview(null);
  };

  const previewAudience = async () => {
    setFormError("");
    try {
      const response = await communicationAnnouncementService.preview(mode, buildPayload(form));
      setPreview(response);
    } catch (err) {
      setPreview(null);
      setFormError(getErrorMessage(err, "Could not preview recipients."));
    }
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!form.title.trim() || !form.body.trim()) return;
    setFormError("");
    const payload = buildPayload(form);
    try {
      const response = await communicationAnnouncementService.preview(mode, payload);
      setPreview(response);
      if (!Number(response?.recipient_count || 0)) {
        setFormError("No active recipients match this audience. Choose a different audience before saving.");
        return;
      }
      await communicationAnnouncementService.create(mode, payload);
      setForm((current) => ({ ...current, title: "", body: "" }));
      setPreview(null);
      setPage(1);
      await load();
    } catch (err) {
      setFormError(getErrorMessage(err, "Could not create announcement."));
    }
  };

  const mutate = async (action) => {
    setError("");
    try {
      await action();
      await load();
    } catch (err) {
      setError(getErrorMessage(err, "Could not update announcement."));
    }
  };

  return (
    <DashboardLayout
      role={mode === "superadmin" ? "superadmin" : "admin"}
      title="Announcements"
      description="One-way broadcasts with concrete delivery records."
    >
    <section className="grid w-full gap-4 sm:gap-5 xl:grid-cols-[26rem_1fr]">
      <form onSubmit={submit} className="space-y-4 rounded-2xl border border-border bg-surface p-3 sm:p-4">
        <Input label="Title" value={form.title} onChange={(event) => update("title", event.target.value)} />
        <label className="block text-sm font-semibold text-text-soft">
          <span className="mb-1.5 block">Message</span>
          <textarea className="input-base min-h-28 resize-y" value={form.body} onChange={(event) => update("body", event.target.value)} />
        </label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-sm font-semibold text-text-soft">
            <span className="mb-1.5 block">Category</span>
            <select className="input-base" value={form.category} onChange={(event) => update("category", event.target.value)}>
              {["general", "academic", "attendance", "event", "finance", "emergency", "system"].map((item) => <option key={item} value={item}>{item.replaceAll("_", " ")}</option>)}
            </select>
          </label>
          <label className="block text-sm font-semibold text-text-soft">
            <span className="mb-1.5 block">Priority</span>
            <select className="input-base" value={form.priority} onChange={(event) => update("priority", event.target.value)}>
              {["low", "normal", "high", "urgent"].map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
        </div>
        <label className="block text-sm font-semibold text-text-soft">
          <span className="mb-1.5 block">Who should receive this announcement?</span>
          <select className="input-base" value={form.audienceType} onChange={(event) => updateAudience(event.target.value)}>
            {audienceOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </label>
        {["selected_teachers", "selected_students", "selected_parents", "selected_tenant_admins"].includes(form.audienceType) ? (
          <SearchableOptionPicker
            label="Build audience"
            placeholder="Type a name or email"
            search={recipientSearch}
            onSearch={setRecipientSearch}
            value={form.actorIds}
            onSelect={toggleAudienceActor}
            options={filteredRecipients}
            selectedOptions={selectedAudienceMembers}
            getOptionLabel={(item) => item.label}
            getOptionMeta={(item) => item.group_label}
            emptyLabel="No allowed audience members match that search"
            multi
          />
        ) : null}
        {["class_students", "class_parents"].includes(form.audienceType) ? (
          <SearchableOptionPicker
            label="Find class"
            placeholder="Type a class name"
            search={classSearch}
            onSearch={setClassSearch}
            value={form.classId}
            onSelect={(value) => update("classId", value)}
            options={filteredClasses}
            getOptionLabel={classLabel}
            getOptionMeta={(item) => item.teacher_name || "Class audience"}
            emptyLabel="No classes match that search"
          />
        ) : null}
        {form.audienceType === "tenant_admins_of_tenants" ? (
          <SearchableOptionPicker
            label="Find tenant"
            placeholder="Type a school name"
            search={tenantSearch}
            onSearch={setTenantSearch}
            value={form.tenantTargetId}
            onSelect={(value) => update("tenantTargetId", value)}
            options={filteredTenants}
            getOptionLabel={(tenant) => tenant.school_name || tenant.name || tenant.email || "Tenant"}
            getOptionMeta={(tenant) => tenant.email || tenant.slug || "Tenant"}
            emptyLabel="No tenants match that search"
          />
        ) : null}
        {preview ? (
          <div className="rounded-lg border border-border bg-surface-muted/40 p-3 text-sm">
            <p className="font-bold text-text">Audience: {preview.audience_label}</p>
            <p className="mt-1 text-text-muted">Recipients: {preview.recipient_count} active recipient{preview.recipient_count === 1 ? "" : "s"}</p>
            {preview.excluded_reasons?.length ? <p className="mt-1 text-warning">{preview.excluded_reasons.join(", ")}</p> : null}
          </div>
        ) : null}
        {formError ? <div className="rounded-lg border border-error/30 bg-error-soft px-3 py-2 text-sm font-semibold text-error">{formError}</div> : null}
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" onClick={previewAudience}>Preview recipients</Button>
          <Button type="submit"><Send className="h-4 w-4" /> Create draft</Button>
        </div>
      </form>

      <main className="space-y-4">
        <div className="flex flex-col gap-3 rounded-2xl border border-border bg-surface p-3 sm:flex-row sm:items-center sm:justify-between sm:p-4">
          <div>
            <h2 className="text-base font-bold text-text">Announcement history</h2>
            <p className="mt-1 text-sm text-text-muted">
              Archived announcements are hidden from this view unless you choose to show them.
            </p>
          </div>
          <label className="flex min-h-11 items-center gap-2 rounded-xl border border-border px-3 text-sm font-semibold text-text-soft">
            <input
              type="checkbox"
              checked={showArchived}
              onChange={(event) => setShowArchived(event.target.checked)}
            />
            Show archived ({archivedCount})
          </label>
        </div>
        {loading ? <LoadingState label="Loading announcements" /> : null}
        {error ? <div className="rounded-xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-semibold text-error">{error}</div> : null}
        {!loading && !error && !visibleItems.length ? (
          <EmptyState
            icon={Megaphone}
            title={items.length ? "Archived announcements are hidden" : "No announcements yet"}
            description={items.length ? "Turn on Show archived when you need to review older announcements." : undefined}
          />
        ) : null}
        {!loading && !error && visibleItems.length ? (
          <div className="mobile-scroll-list grid gap-2 sm:gap-3">
            {visibleItems.map((item) => (
          <article key={item.id} className="rounded-2xl border border-border bg-surface p-3 sm:p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <h2 className="line-clamp-2 text-sm font-bold text-text sm:text-base">{item.title}</h2>
                <p className="mt-1 line-clamp-3 max-w-3xl text-xs text-text-muted sm:text-sm">{item.body}</p>
                <p className="mt-2 text-xs font-semibold uppercase text-text-faint">{item.status}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {item.status === "published" ? (
                  <Button size="sm" variant="outline" onClick={() => mutate(() => communicationAnnouncementService.archive(mode, item.id))}>
                    <Archive className="h-4 w-4" /> Archive
                  </Button>
                ) : null}
                {["draft", "scheduled"].includes(item.status) ? (
                  <>
                    <Button size="sm" variant="outline" onClick={() => mutate(() => communicationAnnouncementService.publish(mode, item.id))}>
                      <Send className="h-4 w-4" /> Publish
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => mutate(() => communicationAnnouncementService.cancel(mode, item.id))}>
                      <XCircle className="h-4 w-4" /> Cancel
                    </Button>
                  </>
                ) : null}
              </div>
            </div>
          </article>
            ))}
          </div>
        ) : null}
        <div className="mobile-list-pagination flex items-center justify-between gap-2">
          <span className="text-xs font-semibold text-text-muted">Page {page} of {pageCount}</span>
          <div className="grid grid-cols-2 gap-2 sm:flex">
            <Button type="button" size="small" variant="outline" disabled={loading || page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>Previous</Button>
            <Button type="button" size="small" variant="outline" disabled={loading || page >= pageCount} onClick={() => setPage((current) => Math.min(pageCount, current + 1))}>Next</Button>
          </div>
        </div>
      </main>
    </section>
    </DashboardLayout>
  );
}
