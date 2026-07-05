import { createRoot } from 'react-dom/client'
import './index.css'
import './styles/mobileDashboard.css'
import App from './App.jsx'

const savedTheme = localStorage.getItem("theme");
const systemTheme = window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
document.documentElement.dataset.theme = savedTheme || systemTheme;

const standaloneQuery = window.matchMedia?.("(display-mode: standalone)");
const updateStandaloneDisplayMode = () => {
  const isStandalone = Boolean(
    standaloneQuery?.matches || window.navigator?.standalone === true
  );
  document.documentElement.dataset.standalonePwa = String(isStandalone);
};

updateStandaloneDisplayMode();
standaloneQuery?.addEventListener?.("change", updateStandaloneDisplayMode);
window.addEventListener("pageshow", updateStandaloneDisplayMode);
document.addEventListener("visibilitychange", updateStandaloneDisplayMode);

createRoot(document.getElementById('root')).render(<App />)
