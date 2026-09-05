from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old in text:
        target.write_text(text.replace(old, new, 1), encoding="utf-8")
        return
    if new and new in text:
        return
    raise RuntimeError(f"Expected patch anchor not found in {path}: {old[:80]!r}")


# Add the canonical placement outcomes to the ORM enum. RECLASSIFIED remains the
# same-level reassignment outcome only; initial placement and level reassignment
# get their own evidence-preserving outcomes.
replace_once(
    "backend/app/modules/students/models.py",
    '    DEMOTED = "demoted"\n    RECLASSIFIED = "reclassified"\n',
    '    DEMOTED = "demoted"\n    CLASS_PLACED = "class_placed"\n    LEVEL_REASSIGNED = "level_reassigned"\n    RECLASSIFIED = "reclassified"\n',
)

# Remove the old batch-assignment response contract. The canonical response now
# lives beside the placement requests in enrollment_schemas.py.
replace_once(
    "backend/app/modules/students/schemas.py",
    '\n\nclass StudentBatchClassAssignmentResponse(OutputBase):\n    updated_student_ids: list[uuid.UUID]\n    target_class_id: uuid.UUID\n    updated_count: int\n',
    "",
)

# TenantAdmin's aggregate router keeps unrelated student lifecycle/account APIs,
# but placement is owned by the dedicated canonical placement router.
replace_once(
    "backend/app/modules/tenant_admins/router.py",
    'from app.modules.students.enrollment_schemas import (\n    StudentBatchClassAssignmentRequest,\n    StudentClassChangeRequest,\n)\nfrom app.modules.students.enrollment_service import StudentEnrollmentService\n',
    "",
)
replace_once(
    "backend/app/modules/tenant_admins/router.py",
    "    StudentBatchClassAssignmentResponse,\n",
    "",
)
replace_once(
    "backend/app/modules/tenant_admins/router.py",
    "    StudentEnrollmentListResponse,\n",
    "",
)
replace_once(
    "backend/app/modules/tenant_admins/router.py",
    '''\n\n@router.post(\n    "/students/batch-class-assignment",\n    response_model=StudentBatchClassAssignmentResponse,\n)\nasync def assign_student_class_batch(\n    payload: StudentBatchClassAssignmentRequest,\n    db: DbSession,\n    current_admin: CurrentTenantAdmin,\n) -> StudentBatchClassAssignmentResponse:\n    return await StudentEnrollmentService.assign_class_batch(\n        db,\n        actor=current_admin,\n        payload=payload,\n    )\n''',
    "",
)
replace_once(
    "backend/app/modules/tenant_admins/router.py",
    '''\n\n@router.get(\n    "/students/{student_id}/enrollments",\n    response_model=StudentEnrollmentListResponse,\n)\nasync def list_student_enrollments(\n    student_id: UUID,\n    db: DbSession,\n    current_admin: CurrentTenantAdmin,\n) -> StudentEnrollmentListResponse:\n    items = await StudentEnrollmentService.list_history(\n        db,\n        tenant_id=current_admin.tenant_id,\n        student_id=student_id,\n    )\n    return StudentEnrollmentListResponse(items=items, total=len(items))\n\n\n@router.post(\n    "/students/{student_id}/class-change",\n    response_model=StudentDetailResponse,\n)\nasync def change_student_class(\n    student_id: UUID,\n    payload: StudentClassChangeRequest,\n    db: DbSession,\n    current_admin: CurrentTenantAdmin,\n) -> StudentDetailResponse:\n    return await StudentEnrollmentService.change_class(\n        db,\n        actor=current_admin,\n        student_id=student_id,\n        payload=payload,\n    )\n''',
    "",
)
Path("backend/app/modules/students/enrollment_service.py").unlink(missing_ok=True)

# Register the new canonical routers without changing unrelated route prefixes.
replace_once(
    "backend/app/main.py",
    "from app.modules.report_cards.bulk_router import router as bulk_report_card_router\n",
    '''from app.modules.report_cards.bulk_router import router as bulk_report_card_router\nfrom app.modules.report_cards.comment_router import (\n    admin_override_router as admin_teacher_comment_override_router,\n    admin_template_router as admin_comment_template_router,\n    teacher_comment_router,\n    teacher_template_router as teacher_comment_template_router,\n)\n''',
)
replace_once(
    "backend/app/main.py",
    "from app.modules.students.router import router as student_router\n",
    "from app.modules.students.router import router as student_router\nfrom app.modules.students.placement_router import router as student_placement_router\n",
)
replace_once(
    "backend/app/main.py",
    '''    app.include_router(\n        tenant_admin_router,\n        prefix=f"{API_V1_PREFIX}/tenant-admin",\n        tags=["Tenant Admin"],\n    )\n''',
    '''    app.include_router(\n        tenant_admin_router,\n        prefix=f"{API_V1_PREFIX}/tenant-admin",\n        tags=["Tenant Admin"],\n    )\n    app.include_router(student_placement_router, prefix=API_V1_PREFIX)\n''',
)
replace_once(
    "backend/app/main.py",
    "    app.include_router(parent_academic_router, prefix=API_V1_PREFIX)\n    app.include_router(fixed_report_card_router, prefix=API_V1_PREFIX)\n",
    '''    app.include_router(parent_academic_router, prefix=API_V1_PREFIX)\n    app.include_router(teacher_comment_router, prefix=API_V1_PREFIX)\n    app.include_router(teacher_comment_template_router, prefix=API_V1_PREFIX)\n    app.include_router(\n        admin_comment_template_router,\n        prefix=API_V1_PREFIX,\n        dependencies=admin_write_guard,\n    )\n    app.include_router(\n        admin_teacher_comment_override_router,\n        prefix=API_V1_PREFIX,\n        dependencies=admin_write_guard,\n    )\n    app.include_router(fixed_report_card_router, prefix=API_V1_PREFIX)\n''',
)
