import { useEffect, useState } from "react";
import { RefreshCw, Wrench, ArrowLeft } from "lucide-react";

import Button from "../../components/ui/Button";
import { clearStoredMaintenanceState, getStoredMaintenanceState, PLATFORM_MAINTENANCE_EVENT } from "../../services/api";

const DEFAULT_MESSAGE = "The platform is temporarily down for maintenance. We are working to restore access as quickly as possible.";

function MaintenanceModePage() {
  const [state, setState] = useState(() => getStoredMaintenanceState());

  useEffect(() => {
    const handleMaintenanceUpdate = (event) => {
      setState(event.detail || getStoredMaintenanceState());
    };

    window.addEventListener(PLATFORM_MAINTENANCE_EVENT, handleMaintenanceUpdate);
    return () => window.removeEventListener(PLATFORM_MAINTENANCE_EVENT, handleMaintenanceUpdate);
  }, []);

  const message = state?.message || DEFAULT_MESSAGE;
  const reason = state?.reason;

  const handleRetry = () => {
    clearStoredMaintenanceState();
    window.location.assign("/login");
  };

  const handleGoBack = () => {
    clearStoredMaintenanceState();
    window.history.back();
  };

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-app px-6 py-12 text-text">
      <div className="w-full max-w-md text-center">
        <div className="mx-auto mb-8 flex h-24 w-24 items-center justify-center rounded-full bg-surface shadow-sm ring-1 ring-border">
          <Wrench className="h-10 w-10 text-text-muted" strokeWidth={1.5} />
        </div>
        
        <h1 className="mb-4 text-3xl font-bold tracking-tight text-text">
          We'll be right back
        </h1>
        
        <p className="mb-8 text-base leading-relaxed text-text-soft">
          {message}
        </p>

        {reason ? (
          <div className="mb-8 rounded-xl bg-surface p-5 text-left text-sm text-text-soft shadow-sm ring-1 ring-border">
            <span className="mb-2 block font-semibold text-text">Maintenance Note</span> 
            {reason}
          </div>
        ) : null}

        <div className="flex flex-col justify-center gap-3 sm:flex-row">
          <Button onClick={handleRetry} className="w-full justify-center sm:w-auto sm:px-8">
            <RefreshCw className="mr-2 h-4 w-4" />
            Try again
          </Button>
          <Button variant="outline" onClick={handleGoBack} className="w-full justify-center sm:w-auto sm:px-8">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Go back
          </Button>
        </div>
      </div>
      
      <div className="fixed bottom-8 text-center text-sm font-medium text-text-muted">
        Your data remains secure during this process.
      </div>
    </main>
  );
}

export default MaintenanceModePage;
