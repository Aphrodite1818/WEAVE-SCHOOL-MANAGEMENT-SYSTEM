import { api, authSession } from "./api";

const MEMBERSHIP_ENDPOINTS = {
  parent: "/parents/accounts/me/memberships",
  teacher: "/teachers/accounts/me/memberships",
};

const normalizeRole = (value) => String(value || "").trim().toLowerCase();

const asItems = (response) => {
  if (Array.isArray(response)) return response;
  return Array.isArray(response?.items) ? response.items : [];
};

const getStoredSummaries = () => {
  const user = authSession.getUser() || {};
  const memberships = user?.memberships || user?.meta?.memberships;
  return Array.isArray(memberships) ? memberships : [];
};

const getMembershipId = (membership) =>
  membership?.membership_id || membership?.id || null;

const getMembershipStatus = (membership) =>
  membership?.membership_status || membership?.status || "unknown";

const normalizeMembership = (membership, storedSummary) => ({
  membership_id: getMembershipId(membership),
  tenant_id: membership?.tenant_id || storedSummary?.tenant_id || null,
  tenant_name:
    membership?.tenant_name ||
    membership?.school_name ||
    storedSummary?.tenant_name ||
    storedSummary?.school_name ||
    "Unavailable school",
  tenant_logo_url:
    membership?.tenant_logo_url ||
    membership?.logo_url ||
    storedSummary?.tenant_logo_url ||
    null,
  membership_status: getMembershipStatus(membership),
  joined_at: membership?.joined_at || null,
  ended_at: membership?.ended_at || null,
});

export const membershipService = {
  getStoredMemberships() {
    return getStoredSummaries().map((membership) =>
      normalizeMembership(membership, membership),
    );
  },

  async listMemberships(role) {
    const normalizedRole = normalizeRole(role);
    const endpoint = MEMBERSHIP_ENDPOINTS[normalizedRole];
    if (!endpoint) return { items: [], total: 0 };

    const storedSummaries = getStoredSummaries();
    const storedById = new Map(
      storedSummaries.map((membership) => [
        String(getMembershipId(membership) || ""),
        membership,
      ]),
    );
    const response = await api.get(endpoint);
    const items = asItems(response).map((membership) => {
      const membershipId = String(getMembershipId(membership) || "");
      return normalizeMembership(membership, storedById.get(membershipId));
    });

    return {
      items,
      total: Number(response?.total ?? items.length),
    };
  },
};

export default membershipService;
