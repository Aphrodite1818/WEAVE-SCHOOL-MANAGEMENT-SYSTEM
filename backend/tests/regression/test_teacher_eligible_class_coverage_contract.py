from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "app" / "modules" / "student_academics" / "curriculum_v2_service.py"


class TeacherEligibleClassCoverageContractTests(unittest.TestCase):
    def test_eligible_class_contract_protects_current_and_scheduled_assignments(self):
        source = SERVICE.read_text(encoding="utf-8")
        start = source.index("async def eligible_classes_for_subject")
        end = source.index("async def resolved_class_subject_responses", start)
        block = source[start:end]
        self.assertIn("protected_assignments", block)
        self.assertIn("TeacherAssignment.effective_to.is_(None)", block)
        self.assertIn("TeacherAssignment.effective_to >= date.today()", block)
        self.assertNotIn("TeacherAssignment.is_active.is_(True)", block)
        self.assertIn("already_assigned=classroom.id in protected_assignments", block)

    def test_contract_still_uses_canonical_resolver_for_eligibility(self):
        source = SERVICE.read_text(encoding="utf-8")
        start = source.index("async def eligible_classes_for_subject")
        end = source.index("async def resolved_class_subject_responses", start)
        block = source[start:end]
        self.assertIn("CurriculumResolutionService.resolve_class_subjects", block)


if __name__ == "__main__":
    unittest.main()
