import { api, authSession } from "./api";

const ROLE_CONFIG = {
  admin: {
    actorType: "tenant_admin",
    statusEndpoint: "/tenant-admin/onboarding-status",
    submitEndpoint: "/tenant-admin/tenant/onboarding",
    submitMethod: "patch",
  },
  teacher: {
    actorType: "teacher",
    statusEndpoint: "/teachers/accounts/me/onboarding-status",
    submitEndpoint: "/teachers/accounts/me/onboarding",
    submitMethod: "post",
  },
  parent: {
    actorType: "parent",
    statusEndpoint: "/parents/accounts/me/onboarding-status",
    submitEndpoint: "/parents/accounts/me/onboarding",
    submitMethod: "post",
  },
  student: {
    actorType: "student",
    statusEndpoint: "/students/me/onboarding-status",
    submitEndpoint: "/students/me/onboarding",
    submitMethod: "post",
  },
};

const ACTOR_ROLE_MAP = {
  tenant_admin: "admin",
  teacher: "teacher",
  teacher_account: "teacher",
  parent: "parent",
  parent_account: "parent",
  student: "student",
  superadmin: "superadmin",
};

const ID_FIELD_BY_ROLE = {
  admin: "tenant_id",
  teacher: "teacher_id",
  parent: "parent_id",
  student: "student_id",
};

export const normalizeRole = (role) => {
  const normalizedRole = String(role || "").trim().toLowerCase();
  return ACTOR_ROLE_MAP[normalizedRole] || normalizedRole;
};

export const roleFromActorType = (actorType) =>
  ACTOR_ROLE_MAP[String(actorType || "").trim().toLowerCase()] || null;

const getRoleConfig = (role) => ROLE_CONFIG[normalizeRole(role)] || null;

const buildSessionUserFromStatus = (role, status, currentUser = authSession.getUser()) => {
  const normalizedRole = normalizeRole(role);
  const roleConfig = getRoleConfig(normalizedRole);

  if (!roleConfig || !status) return currentUser;

  const nextUser = {
    ...(currentUser || {}),
    role: normalizedRole,
    actor_type: currentUser?.actor_type || roleConfig.actorType,
  };

  const idField = ID_FIELD_BY_ROLE[normalizedRole];
  if (idField && status[idField]) {
    nextUser.id = status[idField];
  }

  if (normalizedRole === "admin") {
    nextUser.tenant_id = status.tenant_id;
    nextUser.tenant = {
      ...(nextUser.tenant || {}),
      id: status.tenant_id,
      school_name: status.current_values?.school_name || nextUser.tenant?.school_name,
      email: status.current_values?.email || nextUser.tenant?.email,
      onboarding_completed: status.onboarding_completed,
    };
    nextUser.email = status.current_values?.email || nextUser.email;
    nextUser.onboarding_completed = status.onboarding_completed;
  } else if (normalizedRole === "student") {
    nextUser.admission_number =
      status.current_values?.admission_number || nextUser.admission_number;
    nextUser.first_name = status.current_values?.first_name || nextUser.first_name;
    nextUser.last_name = status.current_values?.last_name || nextUser.last_name;
    nextUser.profile_status = status.profile_status;
  } else {
    nextUser.email = status.current_values?.email || nextUser.email;
    nextUser.first_name = status.current_values?.first_name || nextUser.first_name;
    nextUser.last_name = status.current_values?.last_name || nextUser.last_name;
    nextUser.profile_completed = status.profile_completed;
    nextUser.onboarding_required = !status.profile_completed;
  }

  authSession.setUser(nextUser, {
    remember: authSession.getRememberPreference?.() ?? true,
  });
  authSession.setRole(normalizedRole, {
    remember: authSession.getRememberPreference?.() ?? true,
  });
  return nextUser;
};

export const onboardingService = {
  normalizeRole,

  roleFromActorType,

  getCurrentRole() {
    return normalizeRole(authSession.getUser()?.role || authSession.getRole());
  },

  supportsRole(role) {
    return Boolean(getRoleConfig(role));
  },

  async getOnboardingStatus(role = this.getCurrentRole()) {
    const roleConfig = getRoleConfig(role);
    if (!roleConfig) return null;

    const status = await api.get(roleConfig.statusEndpoint);
    buildSessionUserFromStatus(role, status);
    return status;
  },

  async submitOnboarding(role = this.getCurrentRole(), payload) {
    const roleConfig = getRoleConfig(role);
    if (!roleConfig) {
      throw new Error("Unsupported onboarding role.");
    }

    const submit = api[roleConfig.submitMethod] || api.patch;
    return submit(roleConfig.submitEndpoint, payload);
  },

  updateSessionUserFromStatus(role, status) {
    return buildSessionUserFromStatus(role, status);
  },
};
