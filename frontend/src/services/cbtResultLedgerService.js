import { api } from "./api";

const tenantAdminBasePath = "/tenant-admin/cbt/result-ingestions";
const superadminBasePath = "/superadmin/cbt/result-ingestions";

const withParams = (params, requestOptions = {}) => ({
  ...requestOptions,
  params,
});

const encodedBatchPath = (basePath, batchRecordId) =>
  `${basePath}/${encodeURIComponent(batchRecordId)}`;

const getTenantFilterOptions = (requestOptions) =>
  api.get(`${tenantAdminBasePath}/filter-options`, requestOptions);

const getSuperadminFilterOptions = (tenantId, requestOptions) =>
  api.get(
    `${superadminBasePath}/filter-options`,
    withParams({ tenant_id: tenantId }, requestOptions),
  );

export const cbtResultLedgerService = {
  getTenantFilterOptions,
  getSuperadminFilterOptions,
  getFilterOptions: (params = {}, requestOptions) =>
    params?.tenant_id
      ? getSuperadminFilterOptions(params.tenant_id, requestOptions)
      : getTenantFilterOptions(requestOptions),

  listTenantBatches: (params = {}, requestOptions) =>
    api.get(tenantAdminBasePath, withParams(params, requestOptions)),
  getTenantBatch: (batchRecordId, requestOptions) =>
    api.get(encodedBatchPath(tenantAdminBasePath, batchRecordId), requestOptions),
  listTenantBatchItems: (batchRecordId, params = {}, requestOptions) =>
    api.get(
      `${encodedBatchPath(tenantAdminBasePath, batchRecordId)}/items`,
      withParams(params, requestOptions),
    ),

  listSuperadminBatches: (params = {}, requestOptions) =>
    api.get(superadminBasePath, withParams(params, requestOptions)),
  getSuperadminBatch: (batchRecordId, requestOptions) =>
    api.get(encodedBatchPath(superadminBasePath, batchRecordId), requestOptions),
  listSuperadminBatchItems: (batchRecordId, params = {}, requestOptions) =>
    api.get(
      `${encodedBatchPath(superadminBasePath, batchRecordId)}/items`,
      withParams(params, requestOptions),
    ),
};

export default cbtResultLedgerService;
