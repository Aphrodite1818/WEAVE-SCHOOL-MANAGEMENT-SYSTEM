from pathlib import Path

path = Path("frontend/src/features/academic-admin/ReportCardsWorkspace.jsx")
content = path.read_text(encoding="utf-8")
old = 'import { CheckCircle2, Eye, FileText, RefreshCw, Search, TriangleAlert } from "lucide-react";\n'
new = 'import { CheckCircle2, Eye, RefreshCw, Search, TriangleAlert } from "lucide-react";\n'
if old not in content:
    raise RuntimeError("Expected ReportCardsWorkspace import was not found.")
path.write_text(content.replace(old, new, 1), encoding="utf-8")
print("Removed the unused report-card icon import.")
