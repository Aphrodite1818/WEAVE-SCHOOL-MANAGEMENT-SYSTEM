import { createRoot } from 'react-dom/client'
import './index.css'
import './styles/mobileDashboard.css'
import App from './App.jsx'

const savedTheme = localStorage.getItem("theme");
const systemTheme = window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
document.documentElement.dataset.theme = savedTheme || systemTheme;

createRoot(document.getElementById('root')).render(<App />)
