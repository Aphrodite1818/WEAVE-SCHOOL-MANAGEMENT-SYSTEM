import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Link2,
  Search,
  UserRound,
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
import { getErrorMessage } from "../../services/api";
import { parentService } from "../../services/parentService";

const PAGE_SIZE = 20;
const RELATIONSHIP_OPTIONS = ["father", "mother", "guardian", "sponsor", "other"];

const asItems = (response) =>
  Array.isArray(response) ? response : Array.isArray(response?.items) ? response.items : [];

const personName = (account) => {
  const name = [account?.first_name, account?.last_name].filter(Boolean).join(" ").trim();
  return name || account?.email || "Parent account";
};

const studentName = (student) => {
  const name = [student?.first_name, student?.last_name].filter(Boolean).join(" ").trim();
  return name || student?.admission_number || "Student";
};

const titleCase = (value) =>
  String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

const statusVariant = (status) => {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "active") return "success";
  if (["read_only", "alumni_read_only"].includes(normalized)) return "warning";
  if (normalized === "ended") return "error";
  return "default";
};

function ParentLinkManagementPage() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [memberships, setMemberships] = useState([]);
  const [total, setTotal] = useState(0);
  const [loadingMemberships, setLoadingMemberships] = useState(true);
  const [selectedMembership, setSelectedMembership] = useState(null);
  const [links, setLinks] = useState([]);
  const [loadingLinks, setLoadingLinks] = useState(false);
  const [actionState, setActionState] = useState(null);
  const [busyId, setBusyId] = useState("");
  const { showSuccess, showError, showWarning } = useToast();

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  useEffect(() => {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(async () => {
      setLoadingMemberships(true);
      try {
        const response = await parentService.listMemberships({
          skip: (page - 1) * PAGE_SIZE,
          limit: PAGE_SIZE,
          search: search.trim() || undefined,
          status: "active",
        });
        if (controller.signal.aborted) return;
        setMemberships(asItems(response));
        setTotal(Number(response?.total || 0));
      } catch (requestError) {
        if (!controller.signal.aborted) {
          showError(getErrorMessage(requestError, "Could not load parent memberships."));
        }
      } finally {
        if (!controller.signal.aborted) setLoadingMemberships(false);
      }
    }, search ? 250 : 0);
    return () => {
      window.clearTimeout(timeoutId);
      controller.abort();
    };
  }, [page, search, showError]);

  const loadLinks = async (membership) => {
    setSelectedMembership(membership);
    setLoadingLinks(true);
    try {
      const response = await parentService.listMembershipLinks(membership.id);
      setLinks(asItems(response));
    } catch (requestError) {
      showError(getErrorMessage(requestError, "Could not load child links."));
      setLinks([]);
    } finally {
      setLoadingLinks(false);
    }
  };

  const selectedLabel = useMemo(
    () =>
      selectedMembership
        ? personName(selectedMembership.parent_account || {})
        : "Select a parent membership",
    [selectedMembership],
  );

  const openAction = (mode, item) => {
    setActionState({
      mode,
      item,
      form: {
        reason: "",
        relationship_type: item.link.relationship_type || "guardian",
        is_primary_contact: Boolean(item.link.is_primary_contact),
        receives_academic_updates: item.link.receives_academic_updates !== false,
        receives_fee_updates: item.link.receives_fee_updates !== false,
      },
    });
  };

  const refreshLinks = async () => {
    if (selectedMembership) await loadLinks(selectedMembership);
  };

  const submitAction = async (event) => {
    event.preventDefault();
    if (!actionState) return;
    const { mode, item, form } = actionState;
    if (["end", "reactivate"].includes(mode) && form.reason.trim().length < 3) {
      showWarning("Enter a reason with at least three characters.");
      return;
    }
    setBusyId(item.link.id);
    try {
      if (mode === "end") {
        await parentService.endParentLink(item.link.id, form.reason.trim());
        showSuccess("Parent access to this student ended.");
      } else if (mode === "reactivate") {
        await parentService.reactivateParentLink(item.link.id, {
          reason: form.reason.trim(),
          is_primary_contact: form.is_primary_contact,
          receives_academic_updates: form.receives_academic_updates,
          receives_fee_updates: form.receives_fee_updates,
        });
        showSuccess("Parent access to this student reactivated.");
      } else {
        await parentService.updateParentLink(item.link.id, {
          relationship_type: form.relationship_type,
          is_primary_contact: form.is_primary_contact,
          receives_academic_updates: form.receives_academic_updates,
          receives_fee_updates: form.receives_fee_updates,
        });
        showSuccess("Parent-link preferences updated.");
      }
      setActionState(null);
      await refreshLinks();
    } catch (requestError) {
      showError(getErrorMessage(requestError, "Could not update parent access."));
    } finally {
      setBusyId("");
    }
  };

  return (
    <DashboardLayout
      role="admin"
      title="Parent–Student Access"
      description="End, restore, or update access for one child without changing the parent's other school links."
      actions={
        <Link to="/admin/parents">
          <Button type="button" variant="outline"><ArrowLeft className="h-4 w-4" />Back to parents</Button>
        </Link>
      }
    >
      <div className="grid gap-5 xl:grid-cols-[22rem_minmax(0,1fr)] xl:items-start">
        <Card className="h-fit p-4 sm:p-5 xl:sticky xl:top-4 xl:flex xl:max-h-[calc(100dvh-10rem)] xl:min-h-0 xl:flex-col">
          <div className="relative shrink-0">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
            <Input
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
              placeholder="Search parent name or email"
              className="pl-11"
            />
          </div>

          <div className="mobile-scroll-list mt-4 space-y-2 xl:min-h-0 xl:flex-1 xl:overflow-y-auto xl:pr-1">
            {loadingMemberships ? (
              <LoadingState label="Loading parents..." />
            ) : memberships.length === 0 ? (
              <EmptyState title="No parent memberships" description="Accepted parent invitations appear here." />
            ) : (
              memberships.map((membership) => {
                const account = membership.parent_account || {};
                const active = selectedMembership?.id === membership.id;
                return (
                  <button
                    key={membership.id}
                    type="button"
                    onClick={() => loadLinks(membership)}
                    className={`w-full rounded-2xl border px-3 py-3 text-left transition ${active ? "border-primary bg-primary-subtle" : "border-border bg-surface hover:border-primary/40"}`}
                  >
                    <div className="flex items-start gap-3">
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-primary"><UserRound className="h-4 w-4" /></span>
                      <div className="min-w-0"><p className="truncate text-sm font-semibold text-text">{personName(account)}</p><p className="mt-0.5 truncate text-xs text-text-muted">{account.email}</p><Badge className="mt-2" variant={statusVariant(membership.status)}>{titleCase(membership.status)}</Badge></div>
                    </div>
                  </button>
                );
              })
            )}
          </div>

          <div className="mt-4 flex shrink-0 items-center justify-between border-t border-border/70 pt-4 text-xs text-text-muted">
            <span>{total} membership{total === 1 ? "" : "s"}</span>
            <div className="flex items-center gap-2">
              <Button type="button" size="icon" variant="outline" disabled={loadingMemberships || page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}><ChevronLeft className="h-4 w-4" /></Button>
              <span>{page}/{pageCount}</span>
              <Button type="button" size="icon" variant="outline" disabled={loadingMemberships || page >= pageCount} onClick={() => setPage((current) => Math.min(pageCount, current + 1))}><ChevronRight className="h-4 w-4" /></Button>
            </div>
          </div>
        </Card>

        <div className="space-y-4">
          <Card className="p-5">
            <div className="flex items-start gap-3"><span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary-soft text-primary"><Link2 className="h-5 w-5" /></span><div><h2 className="text-lg font-semibold text-text">{selectedLabel}</h2><p className="mt-1 text-sm text-text-muted">Each card is one independent parent–student access link.</p></div></div>
          </Card>

          {!selectedMembership ? (
            <Card className="p-6"><EmptyState icon={Link2} title="Select a parent" description="Choose a parent membership to inspect its child links." /></Card>
          ) : loadingLinks ? (
            <LoadingState label="Loading child links..." />
          ) : links.length === 0 ? (
            <Card className="p-6"><EmptyState icon={Link2} title="No child links" description="This membership currently has no student-link records." /></Card>
          ) : (
            <section className="mobile-scroll-list grid gap-4 lg:grid-cols-2">
              {links.map((item) => {
                const status = String(item.link.status || "unknown").toLowerCase();
                const busy = busyId === item.link.id;
                return (
                  <Card key={item.link.id} className="flex min-h-[16rem] flex-col p-5">
                    <div className="flex items-start justify-between gap-3"><div><p className="font-semibold text-text">{studentName(item.student)}</p><p className="mt-1 text-xs text-text-muted">{item.student.admission_number} · {titleCase(item.link.relationship_type)}</p></div><Badge variant={statusVariant(status)}>{titleCase(status)}</Badge></div>
                    <div className="mt-4 space-y-2 rounded-2xl bg-surface-muted/30 px-4 py-3 text-sm text-text-muted"><p>Primary contact: {item.link.is_primary_contact ? "Yes" : "No"}</p><p>Academic updates: {item.link.receives_academic_updates ? "Yes" : "No"}</p><p>Fee updates: {item.link.receives_fee_updates ? "Yes" : "No"}</p>{item.link.end_reason ? <p>End reason: {item.link.end_reason}</p> : null}</div>
                    <div className="mt-auto flex flex-wrap gap-2 pt-4">
                      {status === "ended" ? <Button type="button" size="small" variant="success" disabled={busy} onClick={() => openAction("reactivate", item)}>Reactivate link</Button> : <><Button type="button" size="small" variant="outline" disabled={busy} onClick={() => openAction("edit", item)}>Edit preferences</Button><Button type="button" size="small" variant="danger" disabled={busy} onClick={() => openAction("end", item)}>End this link</Button></>}
                    </div>
                  </Card>
                );
              })}
            </section>
          )}
        </div>
      </div>

      <Modal
        open={Boolean(actionState)}
        title={actionState?.mode === "end" ? "End parent–student link" : actionState?.mode === "reactivate" ? "Reactivate parent–student link" : "Edit parent-link preferences"}
        description="This operation affects only the selected child link. Other links remain unchanged."
        onClose={() => !busyId && setActionState(null)}
        closeOnOverlay={!busyId}
      >
        {actionState ? (
          <form onSubmit={submitAction} onTouchStartCapture={(event) => event.stopPropagation()} className="space-y-4">
            {["end", "reactivate"].includes(actionState.mode) ? (
              <label className="block"><span className="mb-1.5 block text-sm font-semibold text-text-soft">Reason</span><textarea className="input-base min-h-28" maxLength={500} value={actionState.form.reason} onChange={(event) => setActionState((current) => ({ ...current, form: { ...current.form, reason: event.target.value } }))} /></label>
            ) : null}
            {actionState.mode !== "end" ? (
              <>
                {actionState.mode === "edit" ? <label className="block"><span className="mb-1.5 block text-sm font-semibold text-text-soft">Relationship</span><select className="input-base" value={actionState.form.relationship_type} onChange={(event) => setActionState((current) => ({ ...current, form: { ...current.form, relationship_type: event.target.value } }))}>{RELATIONSHIP_OPTIONS.map((value) => <option key={value} value={value}>{titleCase(value)}</option>)}</select></label> : null}
                <label className="flex items-center gap-2 text-sm text-text-soft"><input type="checkbox" checked={actionState.form.is_primary_contact} onChange={(event) => setActionState((current) => ({ ...current, form: { ...current.form, is_primary_contact: event.target.checked } }))} />Primary contact</label>
                <label className="flex items-center gap-2 text-sm text-text-soft"><input type="checkbox" checked={actionState.form.receives_academic_updates} onChange={(event) => setActionState((current) => ({ ...current, form: { ...current.form, receives_academic_updates: event.target.checked } }))} />Receive academic updates</label>
                <label className="flex items-center gap-2 text-sm text-text-soft"><input type="checkbox" checked={actionState.form.receives_fee_updates} onChange={(event) => setActionState((current) => ({ ...current, form: { ...current.form, receives_fee_updates: event.target.checked } }))} />Receive fee updates</label>
              </>
            ) : null}
            <div className="flex justify-end gap-2"><Button type="button" variant="outline" disabled={Boolean(busyId)} onClick={() => setActionState(null)}>Cancel</Button><Button type="submit" variant={actionState.mode === "end" ? "danger" : actionState.mode === "reactivate" ? "success" : "default"} disabled={Boolean(busyId)}>{busyId ? "Saving..." : "Confirm"}</Button></div>
          </form>
        ) : null}
      </Modal>
    </DashboardLayout>
  );
}

export default ParentLinkManagementPage;
