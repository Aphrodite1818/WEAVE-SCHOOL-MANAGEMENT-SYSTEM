import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  MailPlus,
  RefreshCw,
  Search,
  ShieldCheck,
  UserRound,
  Users,
} from "lucide-react";

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
import { teacherService } from "../../services/teacherService";

const INVITATION_STATUSES = ["pending", "accepted", "revoked", "expired"];

const roleConfig = {
  teacher: {
    title: "Teacher Directory",
    description:
      "Manage teacher memberships, invitation status, and access to this school without deleting global teacher accounts.",
    membershipLabel: "Teacher memberships",
    inviteLabel: "Invite teacher",
    service: teacherService,
    accountKey: "teacher_account",
    membershipStatuses: ["active", "suspended", "ended"],
  },
  parent: {
    title: "Parent Directory",
    description:
      "Manage parent memberships and school-issued invitations while preserving each parent's global account.",
    membershipLabel: "Parent memberships",
    inviteLabel: "Invite parent",
    service: parentService,
    accountKey: "parent_account",
    membershipStatuses: ["active", "read_only", "inactive"],
  },
};

const asItems = (response) =>
  Array.isArray(response)
    ? response
    : Array.isArray(response?.items)
      ? response.items
      : [];

const displayName = (account) => {
  const name = [account?.first_name, account?.last_name]
    .filter(Boolean)
    .join(" ")
    .trim();
  return name || account?.email || "Account";
};

const badgeVariant = (status) => {
  const value = String(status || "").toLowerCase();
  if (["active", "accepted"].includes(value)) return "success";
  if (["pending", "read_only"].includes(value)) return "warning";
  if (["ended", "inactive", "suspended", "revoked", "expired"].includes(value)) {
    return "error";
  }
  return "default";
};

function MembershipDirectoryPage({ role }) {
  const config = roleConfig[role] || roleConfig.teacher;
  const [activeTab, setActiveTab] = useState("memberships");
  const [memberships, setMemberships] = useState([]);
  const [invitations, setInvitations] = useState([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [actionId, setActionId] = useState("");
  const [error, setError] = useState(null);
  const [lifecycleAction, setLifecycleAction] = useState(null);
  const [reason, setReason] = useState("");
  const { showSuccess, showError, showWarning } = useToast();

  const loadPage = useCallback(async () => {
    setLoading(true);
    setError(null);

    const membershipStatus =
      activeTab === "memberships" ? statusFilter || undefined : undefined;
    const invitationStatus =
      activeTab === "invitations" ? statusFilter || undefined : undefined;

    try {
      const [membershipResponse, invitationResponse] = await Promise.all([
        config.service.listMemberships({
          limit: 100,
          search:
            activeTab === "memberships"
              ? searchQuery.trim() || undefined
              : undefined,
          status: membershipStatus,
        }),
        config.service.listInvitations({
          limit: 100,
          status: invitationStatus,
        }),
      ]);
      setMemberships(asItems(membershipResponse));
      setInvitations(asItems(invitationResponse));
    } catch (err) {
      const message = getErrorMessage(err, `Could not load ${role} directory.`);
      setError(message);
      showError(message);
    } finally {
      setLoading(false);
    }
  }, [
    activeTab,
    config.service,
    role,
    searchQuery,
    showError,
    statusFilter,
  ]);

  useEffect(() => {
    const timeoutId = window.setTimeout(
      loadPage,
      activeTab === "memberships" && searchQuery ? 250 : 0,
    );
    return () => window.clearTimeout(timeoutId);
  }, [activeTab, loadPage, searchQuery]);

  const filteredInvitations = useMemo(() => {
    const normalized = searchQuery.trim().toLowerCase();
    if (!normalized) return invitations;
    return invitations.filter((item) =>
      String(item.invited_email || "").toLowerCase().includes(normalized),
    );
  }, [invitations, searchQuery]);

  const statusOptions =
    activeTab === "memberships"
      ? config.membershipStatuses
      : INVITATION_STATUSES;

  const selectTab = (tabId) => {
    setActiveTab(tabId);
    setStatusFilter("");
  };

  const revokeInvitation = async (item) => {
    setActionId(item.id);
    try {
      await config.service.revokeInvitation(item.id);
      showSuccess("Invitation revoked.");
      await loadPage();
    } catch (err) {
      showError(getErrorMessage(err, "Could not revoke invitation."));
    } finally {
      setActionId("");
    }
  };

  const openLifecycleAction = (membership, action) => {
    setReason("");
    setLifecycleAction({ membership, action });
  };

  const submitLifecycleAction = async () => {
    const normalizedReason = reason.trim();
    if (normalizedReason.length < 3) {
      showWarning("Enter a reason with at least three characters.");
      return;
    }

    const { membership, action } = lifecycleAction;
    setActionId(membership.id);

    try {
      if (action === "suspend") {
        await config.service.suspendMembership(membership.id, normalizedReason);
      } else if (action === "end") {
        await config.service.endMembership(membership.id, normalizedReason);
      } else {
        await config.service.reactivateMembership(
          membership.id,
          normalizedReason,
        );
      }
      showSuccess(
        action === "reactivate"
          ? "Membership reactivated."
          : action === "suspend"
            ? "Membership suspended."
            : "Membership ended.",
      );
      setLifecycleAction(null);
      setReason("");
      await loadPage();
    } catch (err) {
      showError(getErrorMessage(err, "Could not update membership."));
    } finally {
      setActionId("");
    }
  };

  const tabs = [
    {
      id: "memberships",
      label: config.membershipLabel,
      count: memberships.length,
    },
    { id: "invitations", label: "Invitations", count: invitations.length },
  ];

  return (
    <DashboardLayout
      role="admin"
      title={config.title}
      description={config.description}
      actions={
        <Link to={`/admin/create-user?tab=${role}`}>
          <Button type="button">
            <MailPlus className="h-4 w-4" />
            {config.inviteLabel}
          </Button>
        </Link>
      }
    >
      <Modal
        open={Boolean(lifecycleAction)}
        title={
          lifecycleAction?.action === "reactivate"
            ? "Reactivate membership"
            : lifecycleAction?.action === "suspend"
              ? "Suspend membership"
              : "End membership"
        }
        description="This changes access to this school only. The global account remains intact."
        onClose={() => {
          if (actionId) return;
          setLifecycleAction(null);
          setReason("");
        }}
        closeOnOverlay={!actionId}
        footer={
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button
              type="button"
              variant="outline"
              disabled={Boolean(actionId)}
              onClick={() => {
                setLifecycleAction(null);
                setReason("");
              }}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant={
                lifecycleAction?.action === "reactivate"
                  ? "success"
                  : "danger"
              }
              disabled={Boolean(actionId)}
              onClick={submitLifecycleAction}
            >
              {actionId ? "Saving..." : "Confirm change"}
            </Button>
          </div>
        }
      >
        <label className="block">
          <span className="mb-1.5 block text-sm font-semibold text-text-soft">
            Reason
          </span>
          <textarea
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            rows={4}
            maxLength={500}
            className="input-base min-h-28 resize-y"
            placeholder="Explain why this membership access is changing."
          />
        </label>
      </Modal>

      {error ? (
        <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm text-error">
          {error}
        </div>
      ) : null}

      <Card className="p-4 sm:p-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div className="grid flex-1 gap-3 sm:grid-cols-[minmax(0,1fr)_14rem]">
            <div className="relative">
              <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
              <Input
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder={
                  activeTab === "memberships"
                    ? `Search ${role} email or name`
                    : "Search invited email"
                }
                className="pl-11"
              />
            </div>
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
              className="input-base"
            >
              <option value="">All statuses</option>
              {statusOptions.map((status) => (
                <option key={status} value={status}>
                  {status.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </div>
          <Button
            type="button"
            variant="outline"
            onClick={loadPage}
            disabled={loading}
          >
            <RefreshCw
              className={`h-4 w-4 ${loading ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2 rounded-2xl border border-border/70 bg-surface-muted/30 p-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => selectTab(tab.id)}
              className={`min-h-11 rounded-xl px-3 py-2 text-sm font-semibold transition ${
                activeTab === tab.id
                  ? "bg-surface text-primary shadow-sm"
                  : "text-text-muted hover:bg-surface/60 hover:text-text"
              }`}
            >
              {tab.label} ({tab.count})
            </button>
          ))}
        </div>
      </Card>

      {loading && memberships.length === 0 && invitations.length === 0 ? (
        <LoadingState label={`Loading ${role} directory...`} />
      ) : activeTab === "invitations" ? (
        <InvitationList
          role={role}
          invitations={filteredInvitations}
          actionId={actionId}
          onRevoke={revokeInvitation}
        />
      ) : (
        <MembershipList
          role={role}
          memberships={memberships}
          accountKey={config.accountKey}
          actionId={actionId}
          onLifecycleAction={openLifecycleAction}
        />
      )}
    </DashboardLayout>
  );
}

function MembershipList({
  role,
  memberships,
  accountKey,
  actionId,
  onLifecycleAction,
}) {
  if (memberships.length === 0) {
    return (
      <Card className="p-5 sm:p-6">
        <EmptyState
          icon={Users}
          title={`No ${role} memberships found`}
          description="Accepted school invitations will create memberships here."
        />
      </Card>
    );
  }

  return (
    <section className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-3">
      {memberships.map((membership) => {
        const account = membership[accountKey] || {};
        const status = String(membership.status || "unknown").toLowerCase();
        const busy = actionId === membership.id;

        return (
          <Card
            key={membership.id}
            className="flex min-h-[15rem] flex-col p-5"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex min-w-0 items-start gap-3">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary-soft text-primary">
                  <UserRound className="h-5 w-5" />
                </span>
                <div className="min-w-0">
                  <p className="break-words font-semibold text-text">
                    {displayName(account)}
                  </p>
                  <p className="mt-1 break-words text-xs text-text-muted">
                    {account.email || "No email"}
                  </p>
                </div>
              </div>
              <Badge variant={badgeVariant(status)}>
                {status.replaceAll("_", " ")}
              </Badge>
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
                  <p>
                    Joined:{" "}
                    {membership.joined_at
                      ? new Date(membership.joined_at).toLocaleDateString()
                      : "Unknown"}
                  </p>
                  <p>
                    Access:{" "}
                    {status === "read_only"
                      ? "Historical records only"
                      : "Active student links"}
                  </p>
                </>
              )}
            </div>

            <div className="mt-auto flex flex-wrap gap-2 pt-4">
              {role === "teacher" && status === "active" ? (
                <Button
                  type="button"
                  size="small"
                  variant="outline"
                  disabled={busy}
                  onClick={() => onLifecycleAction(membership, "suspend")}
                >
                  Suspend
                </Button>
              ) : null}
              {["active", "read_only", "suspended"].includes(status) ? (
                <Button
                  type="button"
                  size="small"
                  variant="danger"
                  disabled={busy}
                  onClick={() => onLifecycleAction(membership, "end")}
                >
                  End membership
                </Button>
              ) : null}
              {["ended", "inactive", "suspended"].includes(status) ? (
                <Button
                  type="button"
                  size="small"
                  variant="success"
                  disabled={busy}
                  onClick={() => onLifecycleAction(membership, "reactivate")}
                >
                  Reactivate
                </Button>
              ) : null}
            </div>
          </Card>
        );
      })}
    </section>
  );
}

function InvitationList({ role, invitations, actionId, onRevoke }) {
  if (invitations.length === 0) {
    return (
      <Card className="p-5 sm:p-6">
        <EmptyState
          icon={MailPlus}
          title="No invitations found"
          description={`Send a ${role} invitation from Create & Invite.`}
        />
      </Card>
    );
  }

  return (
    <section className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-3">
      {invitations.map((item) => {
        const status = String(item.status || "unknown").toLowerCase();
        return (
          <Card
            key={item.id}
            className="flex min-h-[13rem] flex-col p-5"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="break-words font-semibold text-text">
                  {item.invited_email}
                </p>
                <p className="mt-1 text-xs text-text-muted">
                  Expires{" "}
                  {item.expires_at
                    ? new Date(item.expires_at).toLocaleDateString()
                    : "–"}
                </p>
              </div>
              <Badge variant={badgeVariant(status)}>{status}</Badge>
            </div>
            <div className="mt-4 flex items-start gap-2 rounded-2xl bg-surface-muted/30 px-4 py-3 text-sm text-text-muted">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
              {role === "teacher"
                ? item.job_title ||
                  item.department ||
                  "Teacher school invitation"
                : `${item.relationship_type || "guardian"} invitation for a specific student`}
            </div>
            {status === "pending" ? (
              <Button
                type="button"
                size="small"
                variant="danger"
                className="mt-auto self-start"
                disabled={actionId === item.id}
                onClick={() => onRevoke(item)}
              >
                {actionId === item.id
                  ? "Revoking..."
                  : "Revoke invitation"}
              </Button>
            ) : null}
          </Card>
        );
      })}
    </section>
  );
}

export default MembershipDirectoryPage;
