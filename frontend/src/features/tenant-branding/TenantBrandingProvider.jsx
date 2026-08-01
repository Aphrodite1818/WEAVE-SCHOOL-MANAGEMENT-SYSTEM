import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { authSession } from "../../services/api";
import { tenantBrandingService } from "../../services/tenantBrandingService";
import { schoolName as resolveSchoolName } from "../../utils/user";
import {
  applyBranding, clearAppliedBranding, readCachedBranding,
  validateBrandingResponse, writeCachedBranding,
} from "./tenantBranding";
import { TenantBrandingContext } from "./useTenantBranding";

function currentAppearance() {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

export function TenantBrandingProvider({ children, role, user: userProp }) {
  const user = useMemo(() => userProp || authSession.getUser() || {}, [userProp]);
  const tenantId = user?.tenant_id || user?.tenant?.id || "";
  const eligible = Boolean(tenantId) && role !== "superadmin";
  const scopeRef = useRef(null);
  const requestRef = useRef(0);
  const [branding, setBranding] = useState(() => eligible ? readCachedBranding(tenantId) : null);

  const acceptBranding = useCallback((value, { cache = true } = {}) => {
    const validated = validateBrandingResponse(value, tenantId);
    if (!validated) return false;
    setBranding(validated);
    if (cache) writeCachedBranding(tenantId, validated);
    applyBranding(scopeRef.current, validated, currentAppearance());
    return true;
  }, [tenantId]);

  useEffect(() => {
    const scope = scopeRef.current;
    clearAppliedBranding(scope);
    if (document.documentElement.dataset.startupTenantBranding) {
      clearAppliedBranding(document.documentElement);
      delete document.documentElement.dataset.startupTenantBranding;
    }
    if (!eligible) {
      setBranding(null);
      return undefined;
    }

    const requestId = ++requestRef.current;
    const cached = readCachedBranding(tenantId);
    if (cached) acceptBranding(cached, { cache: false });
    else setBranding(null);

    tenantBrandingService.getEffective().then((response) => {
      if (requestRef.current !== requestId) return;
      if (!acceptBranding(response)) {
        setBranding(null);
        clearAppliedBranding(scope);
      }
    }).catch(() => {
      if (requestRef.current !== requestId) return;
      setBranding(null);
      clearAppliedBranding(scope);
    });

    return () => {
      requestRef.current += 1;
      clearAppliedBranding(scope);
    };
  }, [acceptBranding, eligible, tenantId]);

  useEffect(() => {
    const reapply = () => applyBranding(scopeRef.current, branding, currentAppearance());
    window.addEventListener("weave:accessibility-preferences-changed", reapply);
    const observer = new MutationObserver(reapply);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => {
      observer.disconnect();
      window.removeEventListener("weave:accessibility-preferences-changed", reapply);
    };
  }, [branding]);

  const value = useMemo(() => ({
    branding,
    tenantId,
    schoolName: branding?.school_name || resolveSchoolName(user),
    logoUrl: branding?.logo_url || user?.tenant_logo_url || user?.tenant?.logo_url || "",
    applyResponse: acceptBranding,
  }), [acceptBranding, branding, tenantId, user]);

  return (
    <TenantBrandingContext.Provider value={value}>
      <div ref={scopeRef} data-tenant-branding-scope="true">{children}</div>
    </TenantBrandingContext.Provider>
  );
}
