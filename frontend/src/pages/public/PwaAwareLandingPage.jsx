import { Navigate } from "react-router-dom";

import LandingPage from "./LandingPage";

const isStandalonePwa = () => {
  if (typeof window === "undefined") return false;
  return Boolean(
    window.matchMedia?.("(display-mode: standalone)")?.matches ||
      window.navigator?.standalone === true ||
      document.documentElement.dataset.standalonePwa === "true"
  );
};

function PwaAwareLandingPage() {
  if (isStandalonePwa()) return <Navigate to="/login" replace />;
  return <LandingPage />;
}

export default PwaAwareLandingPage;
