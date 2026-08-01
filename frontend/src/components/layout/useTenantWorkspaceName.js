import { useTenantBranding } from "../../features/tenant-branding/useTenantBranding";

export function useTenantWorkspaceBranding() {
  return useTenantBranding();
}

export default function useTenantWorkspaceName() {
  return useTenantBranding().schoolName;
}
