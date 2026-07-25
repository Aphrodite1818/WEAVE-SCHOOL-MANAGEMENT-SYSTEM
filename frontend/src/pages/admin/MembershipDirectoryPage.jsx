import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BookOpenCheck,
  Check,
  ChevronLeft,
  ChevronRight,
  MailPlus,
  Pencil,
  Search,
  ShieldCheck,
  UserRound,
  Users,
  X,
} from "lucide-react";
import { Link } from "react-router-dom";

import DashboardLayout from "../../components/layout/DashboardLayout";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Input from "../../components/ui/Input";
import Modal from "../../components/ui/Modal";
import { useToast } from "../../hooks/useToast";
import { api, getErrorMessage, parseApiError } from "../../services/api";
import { parentService } from "../../services/parentService";
import { teacherService } from "../../services/teacherService";

const PAGE_SIZE = 24;
const INVITATION_STATUSES = ["pending", "accepted", "revoked", "expired"];

const ROLE_CONFIG = {
  teacher: {
    title: "Teacher Directory",
    description:
      "Manage teacher employment, approved subjects, invitations, and tenant-specific access.",
    membershipLabel: "Teacher memberships",
    inviteLabel: "Invite teacher",
    service: teacherService,
    accountKey: "teacher_account",
    membershipStatuses: ["active", "suspended", "inactive"],
  },
  parent: {
    title: "Parent Directory",
    description:
      "Manage parent memberships, invitation requests, and access without deleting global accounts.",
    membershipLabel: "Parent memberships",
    inviteLabel: "Invite parent",
    service: parentService,
    accountKey: "parent_account",
    membershipStatuses: ["active", "read_only", "inactive"],
  },
};

const asItems = (response) =>
  Array.isArray(response) ? response : Array.isArray(response?.items) ? response.items : [];

const defaultStatusForTab = (tabId) => {
  if (tabId === "memberships") return "active";
  if (tabId === "invitations") return "pending";
  return "";
};

const displayName = (account) => {
  const name = [account?.first_name, account?.last_name].filter(Boolean).join(" ").trim();
  return name || account?.email || "Account";
};

const titleCase = (value) =>
  String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

const badgeVariant = (status) => {
  const value = String(status || "").toLowerCase();
  if (["active", "accepted", "approved"].includes(value)) return "success";
  if (["pending", "read_only"].includes(value)) return "warning";
  if (["inactive", "suspended", "revoked", "expired", "rejected"].includes(value)) return "error";
  return "default";
};

function MembershipDirectoryPage({ role }) {
  const config = ROLE_CONFIG[role] || ROLE_CONFIG.teacher;
  const availableTabs = useMemo(
    () => [
      { id: "memberships", label: config.membershipLabel },
      { id: "invitations", label: "Invitations" },
      ...(role === "parent" ? [{ id: "requests", label: "Pending link requests" }] : []),
    ],
    [config.membershipLabel, role],
  );
  const [activeTab, setActiveTab] = useState("memberships");
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [draftSearch, setDraftSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [draftStatus, setDraftStatus] = useState(() => defaultStatusForTab("memberships"));
  const [appliedStatus, setAppliedStatus] = useState(() => defaultStatusForTab("memberships"));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionId, setActionId] = useState("");
  const [lifecycleState, setLifecycleState] = useState(null);
  const [editState, setEditState] = useState(null);
  const [capabilityState, setCapabilityState] = useState(null);
  const [requestDecision, setRequestDecision] = useState(null);
  const { showSuccess, showError, showWarning } = useToast();

  const statusOptions =
    activeTab === "memberships"
      ? config.membershipStatuses
      : activeTab === "invitations"
        ? INVITATION_STATUSES
        : [];
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const loadPage = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      let response;
      const skip = (page - 1) * PAGE_SIZE;
      if (activeTab === "memberships") {
        response = await config.service.listMemberships({
          skip,
          limit: PAGE_SIZE,
          search: appliedSearch.trim() || undefined,
          status: appliedStatus || undefined,
        });
      } else if (activeTab === "invitations") {
        response = await config.service.listInvitations({
          skip,
          limit: PAGE_SIZE,
          status: appliedStatus || undefined,
        });
      } else {
        response = await parentService.listPendingLinkRequests({ skip, limit: PAGE_SIZE });
      }
      let nextItems = asItems(response);
      if (activeTab === "invitations" && appliedSearch.trim()) {
        const term = appliedSearch.trim().toLowerCase();
        nextItems = nextItems.filter((item) =>
          String(item.invited_email || "").toLowerCase().includes(term),
        );
      }
      setItems(nextItems);
      setTotal(
        Number.isFinite(response?.total)
          ? response.total
          : skip + nextItems.length + (nextItems.length === PAGE_SIZE ? 1 : 0),
      );
    } catch (requestError) {
      const message = getErrorMessage(requestError, `Could not load ${role} directory.`);
      setError(message);
      showError(message);
    } finally {
      setLoading(false);
    }
  }, [activeTab, appliedSearch, appliedStatus, config.service, page, role, showError]);

  useEffect(() => {
    loadPage();
  }, [loadPage]);

  const selectTab = (tabId) => {
    const nextStatus = defaultStatusForTab(tabId);
    setActiveTab(tabId);
    setPage(1);
    setDraftSearch("");
    setAppliedSearch("");
    setDraftStatus(nextStatus);
    setAppliedStatus(nextStatus);
  };

  const applyFilters = (event) => {
    event.preventDefault();
    setPage(1);
    setAppliedSearch(draftSearch);
    setAppliedStatus(draftStatus);
  };

  const clearFilters = () => {
    const nextStatus = defaultStatusForTab(activeTab);
    setPage(1);
    setDraftSearch("");
    setAppliedSearch("");
    setDraftStatus(nextStatus);
    setAppliedStatus(nextStatus);
  };

  const revokeInvitation = async (item) => {
    setActionId(item.id);
    try {
      await config.service.revokeInvitation(item.id);
      showSuccess("Invitation revoked.");
      await loadPage();
    } catch (requestError) {
      showError(getErrorMessage(requestError, "Could not revoke invitation."));
    } finally {
      setActionId("");
    }
  };

  const openLifecycle = async (membership, action) => {
    const state = {
      membership,
      action,
      reason: "",
      impact: null,
      replacementId: "",
      replacements: [],
      loadingImpact: role === "teacher" && action === "end",
    };
    setLifecycleState(state);
    if (role !== "teacher" || action !== "end") return;
    try {
      const [impact, replacementResponse] = await Promise.all([
        teacherService.getOffboardingImpact(membership.id),
        teacherService.listMemberships({ limit: 100, status: "active" }),
      ]);
      setLifecycleState((current) =>
        current
          ? {
              ...current,
              impact,
              replacements: asItems(replacementResponse).filter((item) => item.id !== membership.id),
              loadingImpact: false,
            }
          : current,
      );
    } catch (requestError) {
      showError(getErrorMessage(requestError, "Could not inspect teacher responsibilities."));
      setLifecycleState(null);
    }
  };

  const submitLifecycle = async (event) => {
    event.preventDefault();
    if (!lifecycleState) return;
    const reason = lifecycleState.reason.trim();
    if (reason.length < 3) {
      showWarning("Enter a reason with at least three characters.");
      return;
    }
    const { membership, action } = lifecycleState;
    setActionId(membership.id);
    try {
      if (action === "suspend") {
        await config.service.suspendMembership(membership.id, reason);
      } else if (action === "reactivate") {
        await config.service.reactivateMembership(membership.id, reason);
      } else if (role === "teacher") {
        await teacherService.endMembership(membership.id, reason, lifecycleState.replacementId || null);
      } else {
        await parentService.endMembership(membership.id, reason);
      }
      showSuccess(
        action === "reactivate"
          ? "Membership reactivated."
          : action === "suspend"
            ? "Membership suspended."
            : "Membership ended.",
      );
      setLifecycleState(null);
      await loadPage();
    } catch (requestError) {
      showError(getErrorMessage(requestError, "Could not update membership."));
    } finally {
      setActionId("");
    }
  };

  const openTeacherEdit = (membership) => {
    setEditState({
      membership,
      form: {
        job_title: membership.job_title || "",
        department: membership.department || "",
        employment_type: membership.employment_type || "",
        receive_email_notifications: membership.receive_email_notifications !== false,
        receive_push_notifications: membership.receive_push_notifications !== false,
      },
      fieldErrors: {},
    });
  };

  const submitTeacherEdit = async (event) => {
    event.preventDefault();
    if (!editState) return;
    setActionId(editState.membership.id);
    try {
      await teacherService.updateMembership(editState.membership.id, {
        job_title: editState.form.job_title.trim() || null,
        department: editState.form.department.trim() || null,
        employment_type: editState.form.employment_type.trim() || null,
        receive_email_notifications: editState.form.receive_email_notifications,
        receive_push_notifications: editState.form.receive_push_notifications,
      });
      showSuccess("Teacher membership details updated.");
      setEditState(null);
      await loadPage();
    } catch (requestError) {
      const parsed = parseApiError(requestError, "Could not update teacher membership.");
      setEditState((current) => (current ? { ...current, fieldErrors: parsed.fieldErrors || {} } : current));
      showError(parsed.message);
    } finally {
      setActionId("");
    }
  };

  const openCapabilities = async (membership) => {
    setCapabilityState({ membership, loading: true, subjects: [], selected: new Set() });
    try {
      const [subjectResponse, capabilityResponse] = await Promise.all([
        api.get("/subjects?is_active=true&limit=100"),
        teacherService.listSubjectCapabilities(membership.id),
      ]);
      const selected = new Set(
        asItems(capabilityResponse)
          .filter((item) => item.is_active)
          .map((item) => item.subject_id),
      );
      setCapabilityState({
        membership,
        loading: false,
        subjects: asItems(subjectResponse),
        selected,
      });
    } catch (requestError) {
      showError(getErrorMessage(requestError, "Could not load subject capabilities."));
      setCapabilityState(null);
    }
  };

  const toggleCapability = (subjectId) => {
    setCapabilityState((current) => {
      if (!current) return current;
      const selected = new Set(current.selected);
      if (selected.has(subjectId)) selected.delete(subjectId);
      else selected.add(subjectId);
      return { ...current, selected };
    });
  };

  const saveCapabilities = async () => {
    if (!capabilityState) return;
    setActionId(capabilityState.membership.id);
    try {
      await teacherService.replaceSubjectCapabilities(
        capabilityState.membership.id,
        [...capabilityState.selected],
      );
      showSuccess("Teacher subject capabilities updated.");
      setCapabilityState(null);
    } catch (requestError) {
      showError(getErrorMessage(requestError, "Could not update subject capabilities."));
    } finally {
      setActionId("");
    }
  };

  const decideRequest = async (request, action, reason = null) => {
    setActionId(request.id);
    try {
      await parentService.decideLinkRequest(request.id, {
        action,
        ...(reason ? { reason } : {}),
      });
      showSuccess(action === "approve" ? "Parent link approved." : "Parent link rejected.");
      setRequestDecision(null);
      await loadPage();
    } catch (requestError) {
      showError(getErrorMessage(requestError, "Could not update parent-link request."));
    } finally {
      setActionId("");
    }
  };

  return (
    <DashboardLayout
      role="admin"
      title={config.title}
      description={config.description}
      actions={
        <Link to={`/admin/invitations/${role}`}>
          <Button type="button">
            <MailPlus className="h-4 w-4" />
            {config.inviteLabel}
          </Button>
        </Link>
      }
    >
      {error ? (
        <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm text-error">
          {error}
        </div>
      ) : null}

      <Card className="p-4 sm:p-5">
        <div className={`grid gap-2 ${availableTabs.length === 3 ? "grid-cols-3" : "grid-cols-2"}`}>
          {availableTabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => selectTab(tab.id)}
              className={`min-h-11 rounded-xl px-3 py-2 text-sm font-semibold transition ${activeTab === tab.id ? "bg-primary text-white" : "bg-surface-muted/40 text-text-muted hover:text-text"}`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab !== "requests" ? (
          <form onSubmit={applyFilters} className="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_14rem_auto]">
            <div className="relative">
              <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
              <Input value={draftSearch} onChange={(event) => setDraftSearch(event.target.value)} placeholder={activeTab === "memberships" ? `Search ${role} email or name` : "Search invited email"} className="pl-11" />
            </div>
            <select className="input-base" value={draftStatus} onChange={(event) => setDraftStatus(event.target.value)}>
              <option value="">All statuses</option>
              {statusOptions.map((status) => <option key={status} value={status}>{titleCase(status)}</option>)}
            </select>
            <div className="grid grid-cols-2 gap-2">
              <Button type="submit" size="small">Apply</Button>
              <Button type="button" variant="outline" size="small" onClick={clearFilters}>Clear</Button>
            </div>
          </form>
        ) : null}
      </Card>

      <div className="flex items-center justify-between gap-3 text-sm text-text-muted">
        <span>{total} record{total === 1 ? "" : "s"}</span>
        <span>Page {page} of {pageCount}</span>
      </div>

      {loading ? (
        <LoadingState label={`Loading ${role} directory...`} />
      ) : items.length === 0 ? (
        <Card className="p-6">
          <EmptyState icon={Users} title="No records found" description="Adjust the filters or create an invitation." />
        </Card>
      ) : activeTab === "memberships" ? (
        <section className="directory-card-grid mobile-scroll-list grid gap-4 sm:grid-cols-2 2xl:grid-cols-3">
          {items.map((membership) => {
            const account = membership[config.accountKey] || {};
            const status = String(membership.status || "unknown").toLowerCase();
            const busy = actionId === membership.id;
            return (
              <Card key={membership.id} className="flex min-h-[16rem] flex-col p-5">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 gap-3">
                    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary-soft text-primary"><UserRound className="h-5 w-5" /></span>
                    <div className="min-w-0">
                      <p className="break-words font-semibold text-text">{displayName(account)}</p>
                      <p className="mt-1 break-words text-xs text-text-muted">{account.email || "No email"}</p>
                    </div>
                  </div>
                  <Badge variant={badgeVariant(status)}>{titleCase(status)}</Badge>
                </div>
                <div className="mt-4 space-y-2 rounded-2xl bg-surface-muted/30 px-4 py-3 text-sm text-text-muted">
                  {role === "teacher" ? (
                    <>
                      <p>Staff ID: {membership.staff_id || "Not assigned"}</p>
                      <p>Job title: {membership.job_title || "Not provided"}</p>
                      <p>Department: {membership.department || "Not provided"}</p>
                    </>
                  ) : (
                    <>
                      <p>Joined: {membership.joined_at ? new Date(membership.joined_at).toLocaleDateString() : "Unknown"}</p>
                      <p>Access: {status === "read_only" ? "Historical records only" : status === "active" ? "Active child links" : "Inactive"}</p>
                    </>
                  )}
                </div>
                <div className="mt-auto flex flex-wrap gap-2 pt-4">
                  {role === "teacher" ? (
                    <>
                      <Button type="button" size="small" variant="outline" disabled={busy} onClick={() => openTeacherEdit(membership)}><Pencil className="h-4 w-4" />Edit</Button>
                      <Button type="button" size="small" variant="outline" disabled={busy} onClick={() => openCapabilities(membership)}><BookOpenCheck className="h-4 w-4" />Subjects</Button>
                    </>
                  ) : null}
                  {role === "teacher" && status === "active" ? <Button type="button" size="small" variant="outline" disabled={busy} onClick={() => openLifecycle(membership, "suspend")}>Suspend</Button> : null}
                  {["active", "read_only", "suspended"].includes(status) ? <Button type="button" size="small" variant="danger" disabled={busy} onClick={() => openLifecycle(membership, "end")}>End</Button> : null}
                  {["inactive", "suspended"].includes(status) ? <Button type="button" size="small" variant="success" disabled={busy} onClick={() => openLifecycle(membership, "reactivate")}>Reactivate</Button> : null}
                </div>
              </Card>
            );
          })}
        </section>
      ) : activeTab === "invitations" ? (
        <section className="directory-card-grid mobile-scroll-list grid gap-4 sm:grid-cols-2 2xl:grid-cols-3">
          {items.map((item) => {
            const status = String(item.status || "unknown").toLowerCase();
            return (
              <Card key={item.id} className="flex min-h-[13rem] flex-col p-5">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0"><p className="break-words font-semibold text-text">{item.invited_email}</p><p className="mt-1 text-xs text-text-muted">Expires {item.expires_at ? new Date(item.expires_at).toLocaleDateString() : "–"}</p></div>
                  <Badge variant={badgeVariant(status)}>{titleCase(status)}</Badge>
                </div>
                <div className="mt-4 flex gap-2 rounded-2xl bg-surface-muted/30 px-4 py-3 text-sm text-text-muted"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" />{role === "teacher" ? item.job_title || item.department || "Teacher invitation" : `${titleCase(item.relationship_type || "guardian")} invitation`}</div>
                {status === "pending" ? <Button type="button" size="small" variant="danger" className="mt-auto self-start" disabled={actionId === item.id} onClick={() => revokeInvitation(item)}>{actionId === item.id ? "Revoking..." : "Revoke"}</Button> : null}
              </Card>
            );
          })}
        </section>
      ) : (
        <section className="directory-card-grid mobile-scroll-list grid gap-4 sm:grid-cols-2 2xl:grid-cols-3">
          {items.map((request) => (
            <Card key={request.id} className="flex min-h-[15rem] flex-col p-5">
              <div className="flex items-start justify-between gap-3">
                <div><p className="font-semibold text-text">{request.student_name || request.admission_number_snapshot || "Student"}</p><p className="mt-1 text-xs text-text-muted">{request.parent_email || "Parent account"} · {titleCase(request.relationship_type)}</p></div>
                <Badge variant="warning">Pending</Badge>
              </div>
              <p className="mt-4 rounded-2xl bg-surface-muted/30 px-4 py-3 text-sm text-text-muted">Review the invited parent and student before approving tenant access.</p>
              <div className="mt-auto grid grid-cols-2 gap-2 pt-4">
                <Button type="button" size="small" disabled={actionId === request.id} onClick={() => decideRequest(request, "approve")}><Check className="h-4 w-4" />Approve</Button>
                <Button type="button" size="small" variant="outline" disabled={actionId === request.id} onClick={() => setRequestDecision({ request, reason: "" })}><X className="h-4 w-4" />Reject</Button>
              </div>
            </Card>
          ))}
        </section>
      )}

      <div className="flex justify-end gap-2">
        <Button type="button" size="small" variant="outline" disabled={page <= 1 || loading} onClick={() => setPage((current) => Math.max(1, current - 1))}><ChevronLeft className="h-4 w-4" />Previous</Button>
        <Button type="button" size="small" variant="outline" disabled={page >= pageCount || loading} onClick={() => setPage((current) => Math.min(pageCount, current + 1))}>Next<ChevronRight className="h-4 w-4" /></Button>
      </div>

      <Modal open={Boolean(lifecycleState)} title={lifecycleState ? `${titleCase(lifecycleState.action)} membership` : "Membership lifecycle"} description="This changes access to this school only; the global account remains intact." onClose={() => !actionId && setLifecycleState(null)} closeOnOverlay={!actionId}>
        {lifecycleState ? (
          <form onSubmit={submitLifecycle} className="space-y-4">
            {lifecycleState.loadingImpact ? <LoadingState label="Inspecting active responsibilities..." /> : null}
            {role === "teacher" && lifecycleState.action === "end" && lifecycleState.impact ? (
              <div className="rounded-2xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm text-amber-800">
                <p className="font-semibold">Current responsibilities</p>
                <p className="mt-1">Class head: {lifecycleState.impact.class_teacher_assignments}</p>
                <p>Teacher assignments: {lifecycleState.impact.teacher_assignments}</p>
                <p>Legacy assignments: {lifecycleState.impact.legacy_class_subject_assignments}</p>
              </div>
            ) : null}
            {role === "teacher" && lifecycleState.action === "end" ? (
              <label className="block"><span className="mb-1.5 block text-sm font-semibold text-text-soft">Replacement teacher (optional)</span><select className="input-base" value={lifecycleState.replacementId} onChange={(event) => setLifecycleState((current) => ({ ...current, replacementId: event.target.value }))}><option value="">Release current responsibilities</option>{lifecycleState.replacements.map((item) => <option key={item.id} value={item.id}>{displayName(item.teacher_account)} · {item.job_title || "Teacher"}</option>)}</select></label>
            ) : null}
            <label className="block"><span className="mb-1.5 block text-sm font-semibold text-text-soft">Reason</span><textarea className="input-base min-h-28" maxLength={500} value={lifecycleState.reason} onChange={(event) => setLifecycleState((current) => ({ ...current, reason: event.target.value }))} /></label>
            <div className="flex justify-end gap-2"><Button type="button" variant="outline" disabled={Boolean(actionId)} onClick={() => setLifecycleState(null)}>Cancel</Button><Button type="submit" variant={lifecycleState.action === "reactivate" ? "success" : "danger"} disabled={Boolean(actionId) || lifecycleState.loadingImpact}>{actionId ? "Saving..." : "Confirm"}</Button></div>
          </form>
        ) : null}
      </Modal>

      <Modal open={Boolean(editState)} title="Edit teacher membership" description="Employment details belong to this school membership only." onClose={() => !actionId && setEditState(null)} closeOnOverlay={!actionId}>
        {editState ? (
          <form onSubmit={submitTeacherEdit} className="space-y-4">
            <Input label="Job title" value={editState.form.job_title} error={editState.fieldErrors.job_title} onChange={(event) => setEditState((current) => ({ ...current, form: { ...current.form, job_title: event.target.value } }))} />
            <Input label="Department" value={editState.form.department} error={editState.fieldErrors.department} onChange={(event) => setEditState((current) => ({ ...current, form: { ...current.form, department: event.target.value } }))} />
            <Input label="Employment type" value={editState.form.employment_type} error={editState.fieldErrors.employment_type} onChange={(event) => setEditState((current) => ({ ...current, form: { ...current.form, employment_type: event.target.value } }))} />
            <label className="flex items-center gap-2 text-sm text-text-soft"><input type="checkbox" checked={editState.form.receive_email_notifications} onChange={(event) => setEditState((current) => ({ ...current, form: { ...current.form, receive_email_notifications: event.target.checked } }))} />Email notifications</label>
            <label className="flex items-center gap-2 text-sm text-text-soft"><input type="checkbox" checked={editState.form.receive_push_notifications} onChange={(event) => setEditState((current) => ({ ...current, form: { ...current.form, receive_push_notifications: event.target.checked } }))} />Push notifications</label>
            <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setEditState(null)}>Cancel</Button><Button type="submit" disabled={Boolean(actionId)}>{actionId ? "Saving..." : "Save"}</Button></div>
          </form>
        ) : null}
      </Modal>

      <Modal open={Boolean(capabilityState)} title="Approved teaching subjects" description="Active assignments must be ended or reassigned before their subject approval can be removed." onClose={() => !actionId && setCapabilityState(null)} closeOnOverlay={!actionId}>
        {capabilityState?.loading ? <LoadingState label="Loading subjects..." /> : capabilityState ? (
          <div className="space-y-4"><div className="max-h-80 space-y-2 overflow-y-auto">{capabilityState.subjects.map((subject) => <label key={subject.id} className="flex items-center gap-3 rounded-xl border border-border px-3 py-3 text-sm text-text-soft"><input type="checkbox" checked={capabilityState.selected.has(subject.id)} onChange={() => toggleCapability(subject.id)} /><span><span className="font-semibold text-text">{subject.name}</span>{subject.code ? <span className="ml-2 text-xs text-text-muted">{subject.code}</span> : null}</span></label>)}</div><div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setCapabilityState(null)}>Cancel</Button><Button type="button" disabled={Boolean(actionId)} onClick={saveCapabilities}>{actionId ? "Saving..." : "Save subjects"}</Button></div></div>
        ) : null}
      </Modal>

      <Modal open={Boolean(requestDecision)} title="Reject parent-link request" description="A rejection reason is required for the audit trail." onClose={() => !actionId && setRequestDecision(null)} closeOnOverlay={!actionId}>
        {requestDecision ? <div className="space-y-4"><label className="block"><span className="mb-1.5 block text-sm font-semibold text-text-soft">Reason</span><textarea className="input-base min-h-28" value={requestDecision.reason} maxLength={500} onChange={(event) => setRequestDecision((current) => ({ ...current, reason: event.target.value }))} /></label><div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setRequestDecision(null)}>Cancel</Button><Button type="button" variant="danger" disabled={Boolean(actionId) || requestDecision.reason.trim().length < 3} onClick={() => decideRequest(requestDecision.request, "reject", requestDecision.reason.trim())}>{actionId ? "Rejecting..." : "Reject request"}</Button></div></div> : null}
      </Modal>
    </DashboardLayout>
  );
}

export default MembershipDirectoryPage;
