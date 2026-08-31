import { CheckCircle2, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import DashboardLayout from "../../components/layout/DashboardLayout";
import LoadingState from "../../components/shared/LoadingState";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import { clearSelectedSubscriptionPlan } from "../../features/subscriptions/subscriptionConfig";
import { useSubscription } from "../../features/subscriptions/useSubscription";
import { academicService } from "../../services/academicService";
import { parseApiError } from "../../services/api";
import { subscriptionService } from "../../services/subscriptionService";

function SubscriptionVerifyPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { refreshSubscriptionState } = useSubscription();
  const [status, setStatus] = useState("loading");
  const [message, setMessage] = useState("Verifying your payment...");
  const [successRoute, setSuccessRoute] = useState("/admin/billing");
  const reference = searchParams.get("reference") || searchParams.get("trxref");

  useEffect(() => {
    let mounted = true;
    let redirectTimer = null;

    async function verifyPayment() {
      if (!reference) {
        setStatus("error");
        setMessage(
          "We could not verify this payment. Please try again or contact support.",
        );
        return;
      }

      try {
        const entitlement =
          await subscriptionService.verifyTermPayment(reference);
        const paymentIntent = subscriptionService.consumeTermPaymentIntent({
          academicTermId: entitlement?.academic_term_id,
          reference,
        });
        const returnPath = subscriptionService.safeReturnPath(
          paymentIntent?.returnPath,
          "/admin/billing",
        );
        const shouldOpenTerm =
          paymentIntent?.postPaymentAction === "open_term";
        let openedTerm = false;
        let openTermError = "";

        if (shouldOpenTerm) {
          try {
            await academicService.openTerm(entitlement.academic_term_id);
            openedTerm = true;
          } catch (error) {
            openTermError = parseApiError(
              error,
              "Payment verified, but the academic term still has setup blockers.",
            ).message;
          }
        }

        try {
          await refreshSubscriptionState({ silent: true });
        } catch {
          // Verification already succeeded. A background state refresh must not
          // hide the successful financial result.
        }

        if (!mounted) return;

        clearSelectedSubscriptionPlan();
        setSuccessRoute(returnPath);
        setStatus("success");
        setMessage(
          shouldOpenTerm
            ? openedTerm
              ? "Payment verified and the academic term is now open."
              : `${openTermError} Return to the term workflow to resolve it; your payment is already recorded.`
            : "Payment verified and the plan change is active for the current academic term.",
        );

        redirectTimer = window.setTimeout(() => {
          navigate(returnPath, { replace: true });
        }, 1800);
      } catch (error) {
        if (!mounted) return;

        const apiError = parseApiError(
          error,
          "We could not verify this payment. Please try again or contact support.",
        );
        if (apiError.data?.code === "PAYMENT_RECONCILIATION_REQUIRED") {
          subscriptionService.consumeTermPaymentIntent({
            academicTermId: apiError.data?.academic_term_id,
            reference,
          });
          clearSelectedSubscriptionPlan();
          setSuccessRoute("/admin/billing");
          setStatus("review");
          setMessage(apiError.message);
          return;
        }
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

  const isSuccess = status === "success";
  const needsReview = status === "review";

  return (
    <DashboardLayout
      role="admin"
      title="Term Plan Verification"
      description="Confirming the Paystack payment and applying it to the selected academic term."
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
                isSuccess
                  ? "bg-success-soft text-success"
                  : needsReview
                    ? "bg-warning-soft text-amber-700"
                    : "bg-error-soft text-error"
              }`}
            >
              {isSuccess ? (
                <CheckCircle2 className="h-6 w-6" />
              ) : (
                <TriangleAlert className="h-6 w-6" />
              )}
            </span>

            <h2 className="mt-4 text-xl font-semibold text-text">
              {isSuccess
                ? "Payment verified"
                : needsReview
                  ? "Payment received — review required"
                  : "Verification failed"}
            </h2>
            <p className="mt-2 text-sm leading-6 text-text-muted">{message}</p>

            <div className="mt-6">
              <Button
                variant={isSuccess || needsReview ? "primary" : "outline"}
                onClick={() =>
                  navigate(isSuccess || needsReview ? successRoute : "/admin/billing", {
                    replace: true,
                  })
                }
              >
                {isSuccess
                  ? "Continue"
                  : needsReview
                    ? "Open billing"
                    : "Back to billing"}
              </Button>
            </div>
          </div>
        )}
      </Card>
    </DashboardLayout>
  );
}

export default SubscriptionVerifyPage;
