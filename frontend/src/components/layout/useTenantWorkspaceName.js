import { useEffect, useMemo, useState } from "react";

import { authSession } from "../../services/api";
import { tenantService } from "../../services/tenant.service";
import { schoolName as resolveSchoolName } from "../../utils/user";
import { tenantNameFallbackRoles } from "./navConfig";

function resolveTenantLogo(record) {
  return (
    record?.tenant_logo_url ||
    record?.logo_url ||
    record?.tenant?.logo_url ||
    ""
  );
}

export function useTenantWorkspaceBranding({ user, role }) {
  const storedSchoolName = resolveSchoolName(user);
  const storedLogoUrl = resolveTenantLogo(user);
  const tenantId = user?.tenant_id;
  const [tenantRecord, setTenantRecord] = useState(() => user?.tenant || null);

  useEffect(() => {
    let mounted = true;

    if (!tenantId || !tenantNameFallbackRoles.has(role)) {
      return () => {
        mounted = false;
      };
    }

    async function loadTenantBranding() {
      try {
        const tenant = await tenantService.getTenant(tenantId);
        if (!mounted || !tenant) return;

        setTenantRecord(tenant);

        const currentUser = authSession.getUser() || {};
        const nextSchoolName = resolveSchoolName(tenant);
        const nextLogoUrl = resolveTenantLogo(tenant);

        authSession.setUser(
          {
            ...currentUser,
            school_name:
              nextSchoolName === "School workspace"
                ? currentUser.school_name
                : nextSchoolName,
            tenant_logo_url: nextLogoUrl || currentUser.tenant_logo_url || null,
            tenant,
          },
          {
            remember: Boolean(window.localStorage.getItem("auth_user")),
            notifyChange: false,
          }
        );
      } catch {
        if (mounted) setTenantRecord(user?.tenant || null);
      }
    }

    loadTenantBranding();

    return () => {
      mounted = false;
    };
  }, [role, tenantId, user?.tenant]);

  return useMemo(() => {
    const tenantSchoolName = resolveSchoolName(tenantRecord);
    const schoolName =
      tenantSchoolName !== "School workspace"
        ? tenantSchoolName
        : storedSchoolName;

    return {
      schoolName,
      logoUrl: resolveTenantLogo(tenantRecord) || storedLogoUrl || "",
    };
  }, [storedLogoUrl, storedSchoolName, tenantRecord]);
}

export default function useTenantWorkspaceName({ user, role }) {
  return useTenantWorkspaceBranding({ user, role }).schoolName;
}
