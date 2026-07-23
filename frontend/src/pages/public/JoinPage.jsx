import AuthLayout from "../../components/layout/AuthLayout";
import AccountRegistrationForm from "../../features/auth/AccountRegistrationForm";

function JoinPage() {
  return (
    <AuthLayout
      title="Create your account"
      description="Choose whether you are joining as a teacher or parent. School access is added after you accept an invitation."
      stepLabel="Teacher and parent registration"
      iconPosition="below"
    >
      <AccountRegistrationForm
        role="teacher"
        allowRoleSwitch
        showHeading={false}
      />
    </AuthLayout>
  );
}

export default JoinPage;
