import { useEffect, useState } from "react";
import { CheckCircle2, TriangleAlert } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Card from "../../components/ui/Card";
import Button from "../../components/ui/Button";
import LoadingState from "../../components/shared/LoadingState";
import { parseApiError } from "../../services/api";
import { subscriptionService } from "../../services/subscriptionService";
import {
  clearSelectedSubscriptionPlan,
} from "../../features/subscriptions/subscriptionConfig";
import { academicService } from "../../services/academicService";
import { useSubscription } from "../../features/subscriptions/useSubscription";

function SubscriptionVerifyPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { refreshSubscriptionState } = useSubscription();
  const [status, setStatus] = useState("loading");
  const [message, setMessage] = useState("Verifying your payment...");
  const [successRoute, setSuccessRoute] = useState("/admin/academic/terms");
  const reference = searchParams.get("reference");

  useEffect(() => {
    let mounted = true;
    let redirectTimer = null;

    async function verifyPayment() {
      if (!reference) {
        setStatus("error");
        setMessage(
          "We could not verify this payment. Please try again or contact support."
        );
        return;
      }

      try {
        const entitlement = await subscriptionService.verifyTermPayment(reference);
        const openIntent = subscriptionService.consumeTermPaymentOpenIntent({
          academicTermId: entitlement?.academic_term_id,
          reference,
        });
        const shouldOpenTerm = Boolean(openIntent);
        let openedTerm = false;
        let openTermError = "";

        if (shouldOpenTerm) {
          try {
            await academicService.openTerm(entitlement.academic_term_id);
            openedTerm = true;
          } catch (error) {
            openTermError = parseApiError(
              error,
              "Payment verified, but we could not open the academic term automatically."
            ).message;
          }
        }

        try {
          await refreshSubscriptionState({ silent: true });
        } catch {
          // Verification already succeeded. A refresh failure should not hide that success state.
        }

        if (!mounted) return;

        clearSelectedSubscriptionPlan();
        const nextSuccessRoute = openedTerm
          ? "/admin/dashboard"
          : shouldOpenTerm
            ? "/admin/academic/terms"
            : "/admin/academic/terms";
        setSuccessRoute(nextSuccessRoute);
        setStatus("success");
        setMessage(
          openedTerm
            ? "Payment verified. Your academic term is now open."
            : openTermError ||
                "Payment verified. The plan is funded for this academic term. If the term is still a draft, open it from Academic Terms when setup is ready."
        );
        redirectTimer = window.setTimeout(() => {
          navigate(nextSuccessRoute, { replace: true });
        }, 1800);
      } catch (error) {
        if (!mounted) return;

        const apiError = parseApiError(
          error,
          "We could not verify this payment. Please try again or contact support."
        );
        setStatus("error");
        setMessage(apiError.message);
      }
    }

    verifyPayment();

    return () => {
      mounted = false;
      if (redirectTimer) window.clearTimeout(redirectTimer);
    };
  }, [navigate, reference, refreshSubscriptionState]);

  return (
    <DashboardLayout
      role="admin"
      title="Term Plan Verification"
      description="We are confirming your Paystack payment and attaching the plan to its academic term."
    >
      <Card className="mx-auto max-w-2xl p-6 sm:p-8">
        {status === "loading" ? (
          <div className="space-y-4">
            <LoadingState label="Verifying your payment..." />
            <p className="text-center text-sm font-medium text-text-muted">
              Verifying your payment...
            </p>
          </div>
        ) : (
          <div className="text-center">
            <span
              className={`mx-auto flex h-14 w-14 items-center justify-center rounded-full ${
                status === "success"
                  ? "bg-success-soft text-success"
                  : "bg-error-soft text-error"
              }`}
            >
              {status === "success" ? (
                <CheckCircle2 className="h-6 w-6" />
              ) : (
                <TriangleAlert className="h-6 w-6" />
              )}
            </span>

            <h2 className="mt-4 text-xl font-semibold text-text">
              {status === "success"
                ? "Payment verified"
                : "Verification failed"}
            </h2>
            <p className="mt-2 text-sm leading-6 text-text-muted">{message}</p>

            <div className="mt-6">
              <Button
                variant={status === "success" ? "primary" : "outline"}
                onClick={() =>
                  navigate(
                    status === "success" ? successRoute : "/admin/dashboard",
                    { replace: true }
                  )
                }
              >
                {status === "success"
                  ? successRoute === "/admin/dashboard"
                    ? "Go to dashboard"
                    : "Go to academic terms"
                  : "Back to dashboard"}
              </Button>
            </div>
          </div>
        )}
      </Card>
    </DashboardLayout>
  );
}

export default SubscriptionVerifyPage;
