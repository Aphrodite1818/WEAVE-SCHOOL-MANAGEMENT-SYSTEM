import { api } from "./api";

const tenantAdminBasePath = "/tenant-admin/cbt/result-ingestions";
const superadminBasePath = "/superadmin/cbt/result-ingestions";
const auditFilterOptionsPath = "/cbt/results/audit/filter-options";

const withParams = (params, requestOptions = {}) => ({
  ...requestOptions,
  params,
});

const encodedBatchPath = (basePath, batchRecordId) =>
  `${basePath}/${encodeURIComponent(batchRecordId)}`;

export const cbtResultLedgerService = {
  getFilterOptions: (params = {}, requestOptions) =>
    api.get(auditFilterOptionsPath, withParams(params, requestOptions)),
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
