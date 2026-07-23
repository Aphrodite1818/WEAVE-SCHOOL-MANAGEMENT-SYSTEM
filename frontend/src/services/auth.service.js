import { getValidTokenPayload } from "../utils/auth";
import { api, authSession } from "./api";
import { clearDashboardSessionCache } from "./dashboardSessionCache";
import { onboardingService } from "./onboardingService";
import { tenantService } from "./tenant.service";

const PENDING_VERIFICATION_EMAIL_KEY = "pendingVerificationEmail";

let bootstrapPromise = null;

const resolveAuthScope = ({ actorType, tenantId }) => {
  const normalizedActorType = String(actorType || "").toLowerCase();
  if (normalizedActorType === "superadmin") return "platform";
  if (normalizedActorType === "tenant_admin") return "tenant";
  if (["parent_account", "teacher_account"].includes(normalizedActorType)) {
    return "account";
  }
  if (tenantId) return "membership";
  return "account";
};

const normalizeAuthResponse = (response = {}) => {
  const actorType =
    response.actor_type || response.user?.actor_type || null;
  const accountType =
    response.account_type || response.user?.account_type || null;
  const tenantId =
    response.tenant_id || response.user?.tenant_id || null;
  const role =
    onboardingService.normalizeRole(
      response.role ||
        response.user?.role ||
        onboardingService.roleFromActorType(actorType),
    ) || null;
  const meta = response.user?.meta || {};
  const membershipId =
    ["parent", "teacher"].includes(String(actorType || "").toLowerCase())
      ? response.user?.id || null
      : null;
  const authScope = resolveAuthScope({ actorType, tenantId });

  const currentUser = {
    ...(response.user || {}),
    email: response.email || response.user?.email || null,
    role,
    actor_type: actorType,
    account_type: accountType,
    tenant_id: tenantId,
    membership_id: membershipId,
    auth_scope: authScope,
    membership_selection_required: Boolean(
      meta.membership_selection_required ||
        meta.requires_membership_selection ||
        (authScope === "account" && ["parent", "teacher"].includes(role)),
    ),
    memberships: Array.isArray(meta.memberships) ? meta.memberships : [],
    onboarding_required: Boolean(meta.onboarding_required),
    password_reset_required:
      response.user?.password_reset_required ??
      response.password_reset_required ??
      false,
  };

  return {
    ...response,
    actor_type: actorType,
    account_type: accountType,
    tenant_id: tenantId,
    role,
    auth_scope: authScope,
    membership_id: membershipId,
    membership_selection_required:
      currentUser.membership_selection_required,
    user: currentUser,
  };
};

const resolveMediaUrl = (mediaResponse) =>
  mediaResponse?.render_url ||
  mediaResponse?.signed_url ||
  mediaResponse?.cdn_url ||
  mediaResponse?.public_url ||
  mediaResponse?.media_asset?.signed_url ||
  mediaResponse?.media_asset?.cdn_url ||
  mediaResponse?.media_asset?.public_url ||
  undefined;

const loadPersistedAvatar = async (user) => {
  const actorType = String(
    user?.actor_type || user?.account_type || "",
  ).toLowerCase();

  try {
    if (actorType === "student") {
      return await api.get("/students/me");
    }

    if (actorType === "teacher") {
      return await api.get("/teachers/me");
    }

    if (actorType === "tenant_admin" && user?.id) {
      const media = await api.get("/media/assets/current", {
        params: {
          owner_type: "tenant_admin",
          owner_id: user.id,
          purpose: "tenant_admin_passport",
        },
      });
      const passportPhotoUrl = resolveMediaUrl(media);
      return passportPhotoUrl
        ? { passport_photo_url: passportPhotoUrl }
        : null;
    }
  } catch {
    // Missing optional profile media must never block authentication.
  }

  return null;
};

const hydrateAuthenticatedUser = async (response = {}) => {
  const normalizedResponse = normalizeAuthResponse(response);
  const baseUser = normalizedResponse.user || {};

  const [profileResult, tenantResult] = await Promise.allSettled([
    loadPersistedAvatar(baseUser),
    baseUser.tenant_id
      ? tenantService.getTenant(baseUser.tenant_id)
      : Promise.resolve(null),
  ]);

  const profile =
    profileResult.status === "fulfilled" ? profileResult.value : null;
  const tenant =
    tenantResult.status === "fulfilled" ? tenantResult.value : null;
  const tenantLogoUrl =
    tenant?.logo_url ||
    tenant?.tenant?.logo_url ||
    baseUser.tenant_logo_url ||
    baseUser.tenant?.logo_url ||
    null;

  return {
    ...normalizedResponse,
    user: {
      ...baseUser,
      ...(profile || {}),
      school_name:
        tenant?.school_name ||
        tenant?.tenant?.school_name ||
        baseUser.school_name ||
        null,
      tenant_logo_url: tenantLogoUrl,
      tenant: tenant || baseUser.tenant || null,
    },
  };
};

const persistAuthenticatedUser = (normalizedResponse, remember) => {
  if (
    normalizedResponse.user.email ||
    normalizedResponse.user.role ||
    normalizedResponse.user.actor_type
  ) {
    authSession.setUser(normalizedResponse.user, { remember });
  } else if (normalizedResponse.role) {
    authSession.setRole(normalizedResponse.role, { remember });
  }
};

const restoreSession = async () => {
  try {
    const remember = authSession.getRememberPreference?.() ?? true;
    const existingToken = authSession.getToken();

    if (existingToken && getValidTokenPayload()) {
      authSession.setToken(existingToken, { remember });
    } else {
      authSession.clearToken();

      const tokenResponse = await api.post("/auth/refresh", undefined, {
        auth: false,
        clearAuthOnUnauthorized: false,
        skipAuthRefresh: true,
      });

      if (tokenResponse.access_token) {
        authSession.setToken(tokenResponse.access_token, { remember });
      }
    }

    const sessionResponse = await api.get("/auth/me/session", {
      clearAuthOnUnauthorized: false,
    });

    const normalizedResponse = await hydrateAuthenticatedUser(sessionResponse);
    persistAuthenticatedUser(normalizedResponse, remember);

    return normalizedResponse;
  } catch (error) {
    const status = error?.response?.status;

    if (status === 401) {
      authSession.clear();
      return null;
    }

    throw error;
  }
};

const bootstrapSession = () => {
  if (!bootstrapPromise) {
    bootstrapPromise = restoreSession().finally(() => {
      bootstrapPromise = null;
    });
  }

  return bootstrapPromise;
};

export const authService = {
  login: async (identifier, password, { remember = true } = {}) => {
    const response = await api.post(
      "/auth/login",
      { identifier, password, remember_me: remember },
      { auth: false, skipAuthRefresh: true },
    );

    clearDashboardSessionCache();

    if (response.access_token) {
      authSession.setToken(response.access_token, { remember });
    }

    const normalizedResponse = await hydrateAuthenticatedUser(response);
    persistAuthenticatedUser(normalizedResponse, remember);

    return normalizedResponse;
  },

  selectMembership: async (
    membershipId,
    { remember = authSession.getRememberPreference?.() ?? true } = {},
  ) => {
    const response = await api.post(
      "/auth/select-membership",
      {
        membership_id: membershipId,
        remember_me: remember,
      },
      { skipAuthRefresh: true },
    );

    clearDashboardSessionCache();

    if (response.access_token) {
      authSession.setToken(response.access_token, { remember });
    }

    const normalizedResponse = await hydrateAuthenticatedUser(response);
    persistAuthenticatedUser(normalizedResponse, remember);

    return normalizedResponse;
  },

  requestOtp: (email, purpose = "verification") =>
    api.post(
      "/auth/request-otp",
      { email, purpose },
      { auth: false, clearAuthOnUnauthorized: false, skipAuthRefresh: true },
    ),

  verifyOtp: (email, code, purpose = "verification") =>
    api.post(
      "/auth/verify-otp",
      { email, code, purpose },
      { auth: false, clearAuthOnUnauthorized: false, skipAuthRefresh: true },
    ),

  resetPassword: (email, newPassword, resetToken) =>
    api.post(
      "/auth/reset-password",
      {
        email,
        new_password: newPassword,
        reset_token: resetToken,
      },
      { auth: false, clearAuthOnUnauthorized: false, skipAuthRefresh: true },
    ),

  getInviteStatus: (token) =>
    api.get(`/auth/invite-status?token=${encodeURIComponent(token)}`, {
      auth: false,
      clearAuthOnUnauthorized: false,
      skipAuthRefresh: true,
    }),

  activateTenant: (email, password, token) =>
    api.post(
      "/auth/activate-tenant",
      { email, password, token },
      { auth: false, clearAuthOnUnauthorized: false, skipAuthRefresh: true },
    ),

  acceptInvite: (email, password, token) =>
    api.post(
      "/auth/accept-invite",
      { email, password, token },
      { auth: false, clearAuthOnUnauthorized: false, skipAuthRefresh: true },
    ),

  bootstrapSession,

  logout: async () => {
    clearDashboardSessionCache();
    authSession.clear();

    try {
      await api.post("/auth/logout", undefined, {
        auth: false,
        clearAuthOnUnauthorized: false,
        skipAuthRefresh: true,
      });
    } finally {
      authSession.clear();
    }
  },

  setPendingVerificationEmail: (email) => {
    window.sessionStorage.setItem(PENDING_VERIFICATION_EMAIL_KEY, email || "");
  },

  getPendingVerificationEmail: () =>
    window.sessionStorage.getItem(PENDING_VERIFICATION_EMAIL_KEY) || "",

  clearPendingVerificationEmail: () => {
    window.sessionStorage.removeItem(PENDING_VERIFICATION_EMAIL_KEY);
  },
};
