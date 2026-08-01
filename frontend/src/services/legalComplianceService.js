import { api, authSession } from "./api";

const mergeLegalStatusIntoSession = (status) => {
  const currentUser = authSession.getUser() || {};
  const nextUser = {
    ...currentUser,
    legal_compliance_required: !status?.accepted,
    legal_compliance_policy_version: status?.policy_version || currentUser.legal_compliance_policy_version,
    legal_compliance_accepted_at: status?.accepted_at || currentUser.legal_compliance_accepted_at || null,
  };

  authSession.setUser(nextUser, {
    remember: authSession.getRememberPreference?.() ?? true,
  });
  return nextUser;
};

export const legalComplianceService = {
  async getStatus() {
    const status = await api.get("/legal-compliance/status");
    mergeLegalStatusIntoSession(status);
    return status;
  },

  async accept() {
    const status = await api.post("/legal-compliance/accept");
    mergeLegalStatusIntoSession(status);
    return status;
  },

  updateSession(status) {
    return mergeLegalStatusIntoSession(status);
  },
};
