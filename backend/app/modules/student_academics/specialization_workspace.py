"""Read the exact term's specialization state with a bounded query count."""

from sqlalchemy import select

from app.modules.classes.models import (
    AcademicLevel,
    AcademicLevelDepartment,
    ArmLabel,
    ClassRoom,
    Department,
)
from app.modules.student_academics.curriculum_models import ClassTermDepartmentAssignment
from app.modules.student_academics.curriculum_service import CurriculumResolutionService
from app.modules.student_academics.curriculum_v2_service import AcademicCurriculumService


async def specialization_workspace(db, tenant_id, term_id):
    term = await AcademicCurriculumService._term(db, tenant_id, term_id)
    classes = (
        await db.execute(
            select(ClassRoom, AcademicLevel, ArmLabel)
            .join(AcademicLevel, AcademicLevel.id == ClassRoom.academic_level_id)
            .join(ArmLabel, ArmLabel.id == ClassRoom.arm_label_id)
            .where(
                ClassRoom.tenant_id == tenant_id,
                AcademicLevel.tenant_id == tenant_id,
                ArmLabel.tenant_id == tenant_id,
                ClassRoom.is_active.is_(True),
                ClassRoom.archived_at.is_(None),
            )
            .order_by(AcademicLevel.position, ArmLabel.label)
        )
    ).all()
    assignments = (
        await db.execute(
            select(ClassTermDepartmentAssignment, Department)
            .join(
                AcademicLevelDepartment,
                AcademicLevelDepartment.id
                == ClassTermDepartmentAssignment.academic_level_department_id,
            )
            .join(Department, Department.id == AcademicLevelDepartment.department_id)
            .where(
                ClassTermDepartmentAssignment.tenant_id == tenant_id,
                ClassTermDepartmentAssignment.academic_term_id == term_id,
                AcademicLevelDepartment.tenant_id == tenant_id,
                Department.tenant_id == tenant_id,
            )
        )
    ).all()
    by_class = {row.class_id: (row, department) for row, department in assignments}
    result = []
    for classroom, level, arm in classes:
        assignment, department = by_class.get(classroom.id, (None, None))
        required = CurriculumResolutionService.specialization_is_active(level, term)
        result.append(
            {
                "class_id": classroom.id,
                "academic_level_id": level.id,
                "display_name": f"{level.name} {arm.label}",
                "specialization_required": required,
                "readiness": "not_required"
                if not required
                else "configured"
                if assignment
                else "missing",
                "academic_level_department_id": assignment.academic_level_department_id
                if assignment
                else None,
                "department_name": department.name if department else None,
            }
        )
    return {"academic_term_id": term.id, "status": term.status, "classes": result}
