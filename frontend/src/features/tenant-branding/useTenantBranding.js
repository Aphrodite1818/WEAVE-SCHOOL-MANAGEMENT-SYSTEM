import { createContext, useContext } from "react";

export const TenantBrandingContext = createContext(null);

export function useTenantBranding() {
  const value = useContext(TenantBrandingContext);
  if (!value) throw new Error("useTenantBranding must be used inside TenantBrandingProvider");
  return value;
}
