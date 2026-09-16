from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# Backend service
# ---------------------------------------------------------------------------
service_path = Path("backend/app/modules/student_academics/service.py")
service = service_path.read_text(encoding="utf-8")

service = replace_once(
    service,
    '''        return audit is not None

    @staticmethod
    async def create_teacher_assignment(
''',
    '''        return audit is not None

    @staticmethod
    async def _scheduled_takeover_successor(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        assignment: TeacherAssignment,
        lock: bool = False,
    ) -> TeacherAssignment | None:
        """Return the real scheduled handover successor, not merely a planned end date."""
        if assignment.effective_to is None:
            return None

        history = await StudentAcademicRepository.list_teacher_assignments_for_curriculum_subject(
            db,
            tenant_id,
            assignment.curriculum_subject_id,
            assignment.class_id,
            lock=lock,
        )
        successor = StudentAcademicService._adjacent_scheduled_successor(assignment, history)
        if successor is None:
            return None

        if not await StudentAcademicService._is_scheduled_takeover_relation(
            db,
            tenant_id=tenant_id,
            successor=successor,
            predecessor=assignment,
        ):
            return None

        return successor

    @staticmethod
    async def create_teacher_assignment(
''',
    "insert scheduled takeover helper",
)

preview_start = service.index("    async def teacher_assignment_dependency_preview(")
preview_end = service.index("    async def end_teacher_assignment(", preview_start)
preview = service[preview_start:preview_end]
preview = replace_once(
    preview,
    '''        has_dependencies = any(counts.values())
        blockers: list[str] = []
''',
    '''        has_dependencies = any(counts.values())
        scheduled_takeover = None
        if (
            assignment.state == TeacherAssignmentState.CURRENT
            and assignment.effective_to is not None
        ):
            scheduled_takeover = await StudentAcademicService._scheduled_takeover_successor(
                db,
                tenant_id=tenant_id,
                assignment=assignment,
            )
        blockers: list[str] = []
''',
    "dependency preview takeover detection",
)
preview = replace_once(
    preview,
    '''            can_reassign=(
                assignment.state == TeacherAssignmentState.CURRENT
                and assignment.effective_to is None
            ),
''',
    '''            can_reassign=(
                assignment.state == TeacherAssignmentState.CURRENT
                and scheduled_takeover is None
            ),
''',
    "dependency preview reassign capability",
)
service = service[:preview_start] + preview + service[preview_end:]

reassign_start = service.index("    async def reassign_teacher_assignment(")
reassign_end = service.index("    async def update_scheduled_teacher_assignment(", reassign_start)
reassign = service[reassign_start:reassign_end]
reassign = replace_once(
    reassign,
    '''        if current.effective_to is not None:
            StudentAcademicService._raise_teacher_assignment_conflict(
                "TAKEOVER_ALREADY_SCHEDULED",
                "A teacher takeover is already scheduled for this class and subject.",
            )
''',
    '''        scheduled_takeover = await StudentAcademicService._scheduled_takeover_successor(
            db,
            tenant_id=tenant_id,
            assignment=current,
            lock=True,
        )
        if scheduled_takeover is not None:
            StudentAcademicService._raise_teacher_assignment_conflict(
                "TAKEOVER_ALREADY_SCHEDULED",
                "A teacher takeover is already scheduled for this class and subject.",
            )
''',
    "reassign planned-end false conflict",
)
reassign = replace_once(
    reassign,
    '''        today = date.today()
        effective_from = payload.effective_from or (
            term.start_date if term.start_date is not None and term.start_date > today else today
        )
''',
    '''        today = date.today()
        if payload.effective_from is not None:
            effective_from = payload.effective_from
        elif current.effective_to is not None:
            effective_from = current.effective_to + timedelta(days=1)
        else:
            effective_from = (
                term.start_date if term.start_date is not None and term.start_date > today else today
            )
''',
    "planned-end default takeover date",
)
reassign = replace_once(
    reassign,
    '''        previous_teacher = current.teacher_membership_id
        previous_state = current.state.value
        current.effective_to = effective_from - timedelta(days=1)
''',
    '''        previous_teacher = current.teacher_membership_id
        previous_state = current.state.value
        previous_effective_to = current.effective_to
        current.effective_to = effective_from - timedelta(days=1)
''',
    "preserve previous end date for audit",
)
reassign = replace_once(
    reassign,
    '''            previous_effective_from=current.effective_from,
            previous_effective_to=current.effective_to,
            new_effective_from=replacement.effective_from,
''',
    '''            previous_effective_from=current.effective_from,
            previous_effective_to=previous_effective_to,
            new_effective_from=replacement.effective_from,
''',
    "reassignment audit previous end date",
)
service = service[:reassign_start] + reassign + service[reassign_end:]
service_path.write_text(service, encoding="utf-8")


# ---------------------------------------------------------------------------
# Frontend teacher assignment workspace
# ---------------------------------------------------------------------------
frontend_path = Path("frontend/src/features/academic-admin/TeacherAssignmentsWorkspace.jsx")
frontend = frontend_path.read_text(encoding="utf-8")

frontend = replace_once(
    frontend,
    '''const PAGE_SIZE = 25;
const today = () => new Date().toISOString().slice(0, 10);
''',
    '''const PAGE_SIZE = 25;
const today = () => new Date().toISOString().slice(0, 10);
const nextDate = (value) => {
  const parsed = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return today();
  parsed.setUTCDate(parsed.getUTCDate() + 1);
  return parsed.toISOString().slice(0, 10);
};
''',
    "frontend next-date helper",
)
frontend = replace_once(
    frontend,
    '''const assignmentClassLabel = (item) =>
  [item?.class_name, item?.class_arm].filter(Boolean).join(" ") || "Class";

const formatPeriod = (item) => {
  const period = `${item?.effective_from || "Unknown start"} – ${item?.effective_to || "Present"}`;
  if (!item?.has_scheduled_takeover) return period;
  return `${period} · HANDOVER SCHEDULED to ${item.scheduled_takeover_teacher_name || "incoming teacher"} on ${item.scheduled_takeover_effective_from}`;
};
''',
    '''const assignmentClassLabel = (item) =>
  [item?.class_name, item?.class_arm].filter(Boolean).join(" ") || "Class";

const isMarkedToEnd = (item) =>
  String(item?.status || "").toLowerCase() === "current" &&
  Boolean(item?.effective_to) &&
  !item?.has_scheduled_takeover;

const formatPeriod = (item) => {
  const period = `${item?.effective_from || "Unknown start"} – ${item?.effective_to || "Present"}`;
  if (item?.has_scheduled_takeover) {
    return `${period} · HANDOVER SCHEDULED to ${item.scheduled_takeover_teacher_name || "incoming teacher"} on ${item.scheduled_takeover_effective_from}`;
  }
  if (isMarkedToEnd(item)) return `${period} · MARKED TO END`;
  return period;
};
''',
    "frontend marked-to-end presentation",
)
frontend = replace_once(
    frontend,
    '''  const openReassign = (item) => {
    setReason("");
    setForm((current) => ({
      ...current,
      teacher_membership_id: "",
      effective_from: today(),
    }));
    setReassigning(item);
  };
''',
    '''  const openReassign = (item) => {
    setReason("");
    setForm((current) => ({
      ...current,
      teacher_membership_id: "",
      effective_from: isMarkedToEnd(item) ? nextDate(item.effective_to) : today(),
    }));
    setReassigning(item);
  };
''',
    "frontend takeover default",
)
frontend = replace_once(
    frontend,
    '''              setReason("");
              setEffectiveTo(today());
              setEnding(item);
''',
    '''              setReason("");
              setEffectiveTo(item.effective_to || today());
              setEnding(item);
''',
    "frontend planned-end editor default",
)
frontend = replace_once(
    frontend,
    '''          {form.effective_from === reassigning?.effective_from ? (
            <p className="text-sm text-text-muted">
              This date is the same as when the current teacher started. Weave will treat this as a correction if no academic records already depend on the assignment.
            </p>
          ) : null}
''',
    '''          {isMarkedToEnd(reassigning) ? (
            <p className="text-sm text-text-muted">
              This assignment is marked to end on {reassigning.effective_to}. The takeover defaults to the next day; choosing an earlier date will shorten the current teacher's assignment.
            </p>
          ) : null}
          {form.effective_from === reassigning?.effective_from ? (
            <p className="text-sm text-text-muted">
              This date is the same as when the current teacher started. Weave will treat this as a correction if no academic records already depend on the assignment.
            </p>
          ) : null}
''',
    "frontend reassign planned-end explanation",
)
frontend = replace_once(
    frontend,
    '''            {item.has_scheduled_takeover ? (
              <Badge variant="warning">handover scheduled</Badge>
            ) : null}
''',
    '''            {item.has_scheduled_takeover ? (
              <Badge variant="warning">handover scheduled</Badge>
            ) : null}
            {isMarkedToEnd(item) ? <Badge variant="warning">marked to end</Badge> : null}
''',
    "frontend marked-to-end badge",
)
frontend_path.write_text(frontend, encoding="utf-8")


# ---------------------------------------------------------------------------
# Backend regression tests
# ---------------------------------------------------------------------------
backend_test_path = Path(
    "backend/tests/unit/student_academics/test_teacher_assignment_handover_regressions.py"
)
backend_test = backend_test_path.read_text(encoding="utf-8")
backend_test = replace_once(
    backend_test,
    '''from app.modules.student_academics.schemas import (
    TeacherAssignmentEnd,
    TeacherAssignmentScheduleCancel,
)
''',
    '''from app.modules.student_academics.schemas import (
    TeacherAssignmentEnd,
    TeacherAssignmentReassign,
    TeacherAssignmentScheduleCancel,
)
''',
    "backend test reassign import",
)
backend_test = replace_once(
    backend_test,
    '''        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.count_teacher_assignment_dependencies",
            new=AsyncMock(return_value={"student_results": 0, "report_card_references": 0}),
        ),
    ):
''',
    '''        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.count_teacher_assignment_dependencies",
            new=AsyncMock(return_value={"student_results": 0, "report_card_references": 0}),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.list_teacher_assignments_for_curriculum_subject",
            new=AsyncMock(return_value=[assignment]),
        ),
    ):
''',
    "backend preview history mock",
)
backend_test = replace_once(
    backend_test,
    "    assert preview.can_reassign is False\n",
    "    assert preview.can_reassign is True\n",
    "backend preview reassign assertion",
)
backend_test += '''

@pytest.mark.asyncio
async def test_reassign_planned_end_defaults_takeover_to_next_day() -> None:
    today = date.today()
    tenant_id = uuid.uuid4()
    class_id = uuid.uuid4()
    curriculum_subject_id = uuid.uuid4()
    replacement_teacher_id = uuid.uuid4()
    planned_end = today + timedelta(days=10)
    current = _assignment(
        tenant_id=tenant_id,
        class_id=class_id,
        curriculum_subject_id=curriculum_subject_id,
        effective_from=today - timedelta(days=30),
        effective_to=planned_end,
    )
    created: list[TeacherAssignment] = []

    async def _create(_db, assignment):
        assignment.id = uuid.uuid4()
        created.append(assignment)
        return assignment

    db = AsyncMock()
    with (
        patch(
            "app.modules.student_academics.service.ensure_academic_write_window",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_teacher_assignment_by_id",
            new=AsyncMock(return_value=current),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._scheduled_takeover_successor",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._load_curriculum_subject_context",
            new=AsyncMock(
                return_value=(
                    SimpleNamespace(id=curriculum_subject_id, subject_id=uuid.uuid4()),
                    SimpleNamespace(academic_level_id=uuid.uuid4()),
                )
            ),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._ensure_curriculum_subject_available_to_class",
            new=AsyncMock(
                return_value=SimpleNamespace(
                    id=uuid.uuid4(),
                    start_date=today - timedelta(days=60),
                    end_date=today + timedelta(days=60),
                )
            ),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._validate_teacher_capability",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._ensure_backdated_assignment_change_safe",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_later_teacher_assignments",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.save_teacher_assignment",
            new=AsyncMock(side_effect=lambda _db, row: row),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.create_teacher_assignment",
            new=AsyncMock(side_effect=_create),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._record_teacher_assignment_audit",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._build_teacher_assignment_response",
            new=AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4())),
        ),
    ):
        await StudentAcademicService.reassign_teacher_assignment(
            db,
            tenant_id,
            current.id,
            TeacherAssignmentReassign(
                teacher_membership_id=replacement_teacher_id,
                academic_term_id=uuid.uuid4(),
                effective_from=None,
                reason="Replace teacher after planned end",
            ),
        )

    assert len(created) == 1
    replacement = created[0]
    assert replacement.effective_from == planned_end + timedelta(days=1)
    assert current.effective_to == planned_end


@pytest.mark.asyncio
async def test_reassign_still_blocks_a_real_scheduled_takeover() -> None:
    today = date.today()
    current = _assignment(
        effective_from=today - timedelta(days=30),
        effective_to=today + timedelta(days=10),
    )
    successor = _assignment(
        tenant_id=current.tenant_id,
        class_id=current.class_id,
        curriculum_subject_id=current.curriculum_subject_id,
        effective_from=current.effective_to + timedelta(days=1),
    )
    db = AsyncMock()

    with (
        patch(
            "app.modules.student_academics.service.ensure_academic_write_window",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_teacher_assignment_by_id",
            new=AsyncMock(return_value=current),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._scheduled_takeover_successor",
            new=AsyncMock(return_value=successor),
        ),
    ):
        with pytest.raises(ConflictException, match="takeover is already scheduled"):
            await StudentAcademicService.reassign_teacher_assignment(
                db,
                current.tenant_id,
                current.id,
                TeacherAssignmentReassign(
                    teacher_membership_id=uuid.uuid4(),
                    academic_term_id=uuid.uuid4(),
                    reason="Attempt duplicate takeover",
                ),
            )
'''
backend_test_path.write_text(backend_test, encoding="utf-8")


# ---------------------------------------------------------------------------
# Frontend contract coverage
# ---------------------------------------------------------------------------
frontend_test_path = Path("frontend/test/teacher-assignment-level-first-contract.test.js")
frontend_test = frontend_test_path.read_text(encoding="utf-8")
frontend_test += '''

test("planned assignment endings remain current but are visibly marked to end", () => {
  assert.match(source, /const isMarkedToEnd = \\(item\\) =>/);
  assert.match(source, /MARKED TO END/);
  assert.match(source, />marked to end<\\/Badge>/);
});

test("reassigning a marked-to-end assignment defaults takeover to the next day", () => {
  assert.match(
    source,
    /effective_from: isMarkedToEnd\\(item\\) \\? nextDate\\(item\\.effective_to\\) : today\\(\\)/,
  );
  assert.match(source, /The takeover defaults to the next day/);
  assert.match(source, /setEffectiveTo\\(item\\.effective_to \\|\\| today\\(\\)\\)/);
});
'''
frontend_test_path.write_text(frontend_test, encoding="utf-8")
