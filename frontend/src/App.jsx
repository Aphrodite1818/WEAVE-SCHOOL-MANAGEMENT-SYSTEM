import AppRoutes from "./routes"
import ErrorBoundary from "./components/shared/ErrorBoundary"
import MobileStartupScreen from "./components/shared/MobileStartupScreen"
import ToastHost from "./components/ui/Toast"

function App(){
  return (
    <ErrorBoundary>
      <MobileStartupScreen />
      <AppRoutes />
      <ToastHost />
    </ErrorBoundary>
  )
}

export default App;
