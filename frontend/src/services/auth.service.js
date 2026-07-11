import { api, authSession } from "./api";
import { clearDashboardSessionCache } from "./dashboardSessionCache";
import { onboardingService } from "./onboardingService";
import { tenantService } from "./tenant.service";

const PENDING_VERIFICATION_EMAIL_KEY = "pendingVerificationEmail";

let bootstrapPromise = null;

const normalizeAuthResponse = (response = {}) => {
    const role =
        onboardingService.normalizeRole(
            response.role || response.user?.role || onboardingService.roleFromActorType(response.actor_type)
        ) || null;

    const currentUser = {
        ...(response.user || {}),
        email: response.email || response.user?.email || null,
        role,
        actor_type: response.actor_type || response.user?.actor_type || null,
        password_reset_required:
            response.user?.password_reset_required ?? response.password_reset_required ?? false,
    };

    return {
        ...response,
        role,
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
    const actorType = String(user?.actor_type || user?.account_type || "").toLowerCase();

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
            return passportPhotoUrl ? { passport_photo_url: passportPhotoUrl } : null;
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
        baseUser.tenant_id ? tenantService.getTenant(baseUser.tenant_id) : Promise.resolve(null),
    ]);

    const profile = profileResult.status === "fulfilled" ? profileResult.value : null;
    const tenant = tenantResult.status === "fulfilled" ? tenantResult.value : null;
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

        const tokenResponse = await api.post(
            "/auth/refresh",
            undefined,
            {
                auth: false,
                clearAuthOnUnauthorized: false,
                skipAuthRefresh: true,
            }
        );

        if (tokenResponse.access_token) {
            authSession.setToken(tokenResponse.access_token, { remember });
        }

        const sessionResponse = await api.get("/auth/me/session", {
            clearAuthOnUnauthorized: false,
        });

        const normalizedResponse = await hydrateAuthenticatedUser(sessionResponse);
        persistAuthenticatedUser(normalizedResponse, remember);

        return normalizedResponse;
    } catch (error) {
        const status = error?.response?.status;

        // A confirmed 401 means the refresh session is no longer valid.
        // Network failures and temporary backend errors must not erase local auth state.
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
            { auth: false, skipAuthRefresh: true }
        );

        clearDashboardSessionCache();

        if (response.access_token) {
            authSession.setToken(response.access_token, { remember });
        }

        const normalizedResponse = await hydrateAuthenticatedUser(response);
        persistAuthenticatedUser(normalizedResponse, remember);

        return normalizedResponse;
    },

    bootstrapSession,

    logout: async () => {
        try {
            await api.post("/auth/logout", undefined, {
                clearAuthOnUnauthorized: false,
                skipAuthRefresh: true,
            });
        } finally {
            clearDashboardSessionCache();
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
