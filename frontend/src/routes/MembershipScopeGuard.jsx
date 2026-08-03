import { Navigate, Outlet, useLocation } from "react-router-dom";

import { authSession } from "../services/api";
import { getValidTokenPayload } from "../utils/auth";

const ACCOUNT_ACTOR_TYPES = new Set(["parent_account", "teacher_account"]);

function MembershipScopeGuard({ role }) {
  const location = useLocation();
  const payload = getValidTokenPayload();
  const user = authSession.getUser() || {};
  const normalizedRole = String(role || "").trim().toLowerCase();
  const actorType = String(
    payload?.actor_type || user?.actor_type || ""
  ).trim().toLowerCase();
  const tenantId = payload?.tenant_id || user?.tenant_id || null;
  const expectedActorType = normalizedRole === "parent" ? "parent" : "teacher";

  if (!payload) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (
    ACCOUNT_ACTOR_TYPES.has(actorType) ||
    actorType !== expectedActorType ||
    !tenantId
  ) {
    return (
      <Navigate
        to={`/${normalizedRole}/schools`}
        replace
        state={{ from: location }}
      />
    );
  }

  return <Outlet />;
}

export default MembershipScopeGuard;
