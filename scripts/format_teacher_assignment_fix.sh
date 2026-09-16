#!/usr/bin/env bash
set -euo pipefail
python -m pip install --quiet ruff==0.16.0
ruff format backend/app/modules/student_academics/service.py backend/tests/unit/student_academics/test_teacher_assignment_handover_regressions.py
git rm -- scripts/format_teacher_assignment_fix.sh .github/workflows/format-teacher-assignment-fix.yml
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add backend/app/modules/student_academics/service.py backend/tests/unit/student_academics/test_teacher_assignment_handover_regressions.py
git commit -m "Format teacher assignment fix"
git push
