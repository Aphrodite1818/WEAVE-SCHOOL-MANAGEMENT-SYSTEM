import { useEffect, useState } from "react";

import { authSession } from "../../services/api";
import { tenantService } from "../../services/tenant.service";
import { schoolName as resolveSchoolName } from "../../utils/user";
import { tenantNameFallbackRoles } from "./navConfig";

export default function useTenantWorkspaceName({ user, role }) {
  const storedSchoolName = resolveSchoolName(user);
  const tenantId = user?.tenant_id;
  const [tenantSchoolName, setTenantSchoolName] = useState("");

  useEffect(() => {
    let mounted = true;
    setTenantSchoolName("");

    if (storedSchoolName !== "School workspace" || !tenantId || !tenantNameFallbackRoles.has(role)) {
      return () => {
        mounted = false;
      };
    }

    async function loadTenantName() {
      try {
        const tenant = await tenantService.getTenant(tenantId);
        if (!mounted) return;

        const nextSchoolName = resolveSchoolName(tenant);
        if (nextSchoolName === "School workspace") return;

        const currentUser = authSession.getUser() || {};
        setTenantSchoolName(nextSchoolName);
        authSession.setUser(
          { ...currentUser, school_name: nextSchoolName, tenant },
          {
            remember: Boolean(window.localStorage.getItem("auth_user")),
            notifyChange: false,
          }
        );
      } catch {
        if (mounted) setTenantSchoolName("");
      }
    }

    loadTenantName();

    return () => {
      mounted = false;
    };
  }, [role, storedSchoolName, tenantId]);

  return tenantSchoolName || storedSchoolName;
}
