import { useEffect, useState } from "react";

import { CATALOGUE_CHANGED_EVENT } from "./pricingCatalogueRuntime";

const readReadyState = () =>
  typeof document !== "undefined" &&
  document.documentElement.dataset.pricingCatalogueReady === "true";

export function usePublicPricingCatalogue() {
  const [ready, setReady] = useState(readReadyState);

  useEffect(() => {
    const handleCatalogueChange = () => setReady(readReadyState());
    window.addEventListener(CATALOGUE_CHANGED_EVENT, handleCatalogueChange);
    return () =>
      window.removeEventListener(
        CATALOGUE_CHANGED_EVENT,
        handleCatalogueChange,
      );
  }, []);

  return ready;
}
