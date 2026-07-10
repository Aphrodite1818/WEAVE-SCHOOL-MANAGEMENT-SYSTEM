import { api, authSession } from "./api";
import { clearDashboardSessionCache } from "./dashboardSessionCache";
import { onboardingService } from "./onboardingService";

const PENDING_VERIFICATION_EMAIL_KEY = "pendingVerificationEmail";

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

        const normalizedResponse = normalizeAuthResponse(response);

        if (
            normalizedResponse.user.email ||
            normalizedResponse.user.role ||
            normalizedResponse.user.actor_type
        ) {
            authSession.setUser(normalizedResponse.user, { remember });
        } else if (normalizedResponse.role) {
            authSession.setRole(normalizedResponse.role, { remember });
        }

        return normalizedResponse;
    },

    bootstrapSession: async () => {
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

            const normalizedResponse = normalizeAuthResponse(sessionResponse);

            if (
                normalizedResponse.user.email ||
                normalizedResponse.user.role ||
                normalizedResponse.user.actor_type
            ) {
                authSession.setUser(normalizedResponse.user, { remember });
            } else if (normalizedResponse.role) {
                authSession.setRole(normalizedResponse.role, { remember });
            }

            return normalizedResponse;
        } catch {
            authSession.clear();
            return null;
        }
    },

    requestOtp: (email, purpose) =>
        api.post("/auth/request-otp", { email, purpose }, { auth: false }),

    verifyOtp: (email, code, purpose) =>
        api.post("/auth/verify-otp", { email, code, purpose }, { auth: false }),

    activateTenant: (email, password, token) =>
        api.post(
            "/auth/activate-tenant",
            { email, password, token },
            { auth: false }
        ),

    getInviteStatus: (token) =>
        api.get(`/auth/invite-status?token=${encodeURIComponent(token)}`, {
            auth: false,
        }),

    acceptInvite: (email, password, token) =>
        api.post(
            "/auth/accept-invite",
            { email, password, token },
            { auth: false }
        ),

    resetPassword: (email, reset_token, new_password) =>
        api.post(
            "/auth/reset-password",
            { email, reset_token, new_password },
            { auth: false }
        ),

    setPendingVerificationEmail: (email) => {
        sessionStorage.setItem(PENDING_VERIFICATION_EMAIL_KEY, email);
    },

    getPendingVerificationEmail: () =>
        sessionStorage.getItem(PENDING_VERIFICATION_EMAIL_KEY),

    clearPendingVerificationEmail: () => {
        sessionStorage.removeItem(PENDING_VERIFICATION_EMAIL_KEY);
    },

    logout: async () => {
        clearDashboardSessionCache();

        try {
            await api.post("/auth/logout", undefined, {
                auth: false,
                clearAuthOnUnauthorized: false,
                skipAuthRefresh: true,
            });
        } catch {
            // Local logout should still complete even if the network request fails.
        } finally {
            authSession.clear();
        }
    },
};
