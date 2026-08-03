import { useSearchParams } from "react-router-dom";

import AuthLayout from "../../components/layout/AuthLayout";
import AccountRegistrationForm from "../../features/auth/AccountRegistrationForm";

const ROLE_CONFIG = {
  parent: {
    title: "Create parent account",
    description:
      "Create one parent account that can securely join multiple school workspaces.",
  },
  teacher: {
    title: "Create teacher account",
    description:
      "Create one teacher account that can securely join multiple school workspaces.",
  },
};

const safeReturnTo = (value) => {
  if (
    typeof value !== "string" ||
    !value.startsWith("/") ||
    value.startsWith("//")
  ) {
    return "";
  }
  return value;
};

function AccountRegisterPage({ role }) {
  const [searchParams] = useSearchParams();
  const resolvedRole = ROLE_CONFIG[role] ? role : "parent";
  const config = ROLE_CONFIG[resolvedRole];
  const returnTo = safeReturnTo(searchParams.get("returnTo"));

  return (
    <AuthLayout
      title={config.title}
      description={config.description}
      stepLabel={`${resolvedRole === "teacher" ? "Teacher" : "Parent"} registration`}
    >
      <AccountRegistrationForm
        role={resolvedRole}
        returnTo={returnTo}
        showHeading={false}
      />
    </AuthLayout>
  );
}

export default AccountRegisterPage;
