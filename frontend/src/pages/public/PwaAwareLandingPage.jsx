import { Navigate } from "react-router-dom";

import LandingPage from "./LandingPage";
import { authSession } from "../../services/api";

const isStandalonePwa = () => {
  if (typeof window === "undefined") return false;
  return Boolean(
    window.matchMedia?.("(display-mode: standalone)")?.matches ||
      window.navigator?.standalone === true ||
      document.documentElement.dataset.standalonePwa === "true"
  );
};

function PwaAwareLandingPage() {
  const hasRememberedSession = Boolean(authSession.getUser());

  if (isStandalonePwa() || hasRememberedSession) {
    return <Navigate to="/login?resume=1" replace />;
  }

  return <LandingPage />;
}

export default PwaAwareLandingPage;
