export const isAssignableClassTeacher = (item) => {
  const account = item?.teacher_account || item?.account || {};
  return (
    String(item?.status || "").toLowerCase() === "active" &&
    String(account.account_status || "").toLowerCase() === "active" &&
    account.is_active === true
  );
};
