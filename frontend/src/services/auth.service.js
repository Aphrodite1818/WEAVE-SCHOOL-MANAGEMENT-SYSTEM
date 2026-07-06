import { api, authSession } from "./api";
import { clearDashboardSessionCache } from "./dashboardSessionCache";
import { onboardingService } from "./onboardingService";

const PENDING_VERIFICATION_EMAIL_KEY = "pendingVerificationEmail";

export const authService = {
    login: async (identifier, password, { remember = true } = {}) => {
        const response = await api.post(
            "/auth/login",
            { identifier, password },
            { auth: false }
        );

        clearDashboardSessionCache();

        if (response.access_token) {
            authSession.setToken(response.access_token, { remember });
        }

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

        if (currentUser.email || currentUser.role || currentUser.actor_type) {
            authSession.setUser(currentUser, { remember });
        } else if (role) {
            authSession.setRole(role, { remember });
        }

        return {
            ...response,
            role,
            user: currentUser,
        };
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
        
    logout: () => {
        clearDashboardSessionCache();
        authSession.clear();
    }
};
