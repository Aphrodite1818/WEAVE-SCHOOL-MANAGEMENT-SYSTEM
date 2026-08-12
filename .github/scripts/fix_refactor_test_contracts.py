from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text()


def write(path: str, text: str) -> None:
    Path(path).write_text(text)


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}: {old[:120]!r}")
    write(path, text.replace(old, new, 1))


# Preserve the existing reconcile result contract while still performing stale
# checkout cleanup as part of reconciliation.
path = "backend/app/modules/subscriptions/term_entitlement_service.py"
text = read(path)
text = text.replace(
    "        abandoned_checkouts = await TermPlanEntitlementService.expire_stale_pending_checkouts(\n",
    "        await TermPlanEntitlementService.expire_stale_pending_checkouts(\n",
    1,
)
text = text.replace(
    '"This academic term still has an active Paystack checkout. "',
    '"This academic term still has a pending Paystack checkout. "',
    1,
)
old = """        return {
            "closed_term_repaired": repaired_closed,
            "safety_expired": safety_expired,
            "pending_checkouts_abandoned": abandoned_checkouts,
        }
"""
new = """        return {"closed_term_repaired": repaired_closed, "safety_expired": safety_expired}
"""
if old not in text:
    raise RuntimeError("reconcile result contract anchor missing")
text = text.replace(old, new, 1)
write(path, text)

# Existing class architecture tests exercise class behavior, not the session
# freeze guard. Mock the guard at the module boundary so those tests remain
# focused; dedicated regression coverage verifies the guard itself.
path = "backend/tests/unit/classes/test_academic_level_architecture.py"
text = read(path)
fixture = '''\n\n@pytest.fixture(autouse=True)\ndef _allow_academic_writes_for_class_unit_tests():\n    with patch(\n        "app.modules.classes.service.ensure_academic_write_window",\n        new=AsyncMock(),\n    ):\n        yield\n'''
anchor = "\n\ndef test_classroom_contract_requires_explicit_level_and_arm() -> None:\n"
if fixture not in text:
    if anchor not in text:
        raise RuntimeError("class test fixture anchor missing")
    text = text.replace(anchor, fixture + anchor, 1)
write(path, text)

# Same separation for assignment lifecycle tests.
path = "backend/tests/unit/student_academics/test_teacher_assignment_lifecycle.py"
text = read(path)
fixture = '''\n\n@pytest.fixture(autouse=True)\ndef _allow_academic_writes_for_assignment_unit_tests():\n    with patch(\n        "app.modules.student_academics.service.ensure_academic_write_window",\n        new=AsyncMock(),\n    ):\n        yield\n'''
anchor = "\n\ndef _assignment() -> TeacherAssignment:\n"
if fixture not in text:
    if anchor not in text:
        raise RuntimeError("assignment test fixture anchor missing")
    text = text.replace(anchor, fixture + anchor, 1)
write(path, text)

# Report-card regeneration now intentionally reads historical enrollment. Give
# the existing unit test a minimal DB result carrying that historical class.
path = "backend/tests/unit/report_cards/test_report_card_print_security.py"
text = read(path)
text = text.replace(
    "from unittest.mock import AsyncMock\n",
    "from unittest.mock import AsyncMock, MagicMock\n",
    1,
)
old = """    new_card = await ReportCardService._create_card_from_results(
        SimpleNamespace(),
        actor,
"""
new = """    enrollment_result = MagicMock()
    enrollment_result.scalar_one_or_none.return_value = SimpleNamespace(
        class_id=existing.class_id
    )
    db = MagicMock()
    db.execute = AsyncMock(return_value=enrollment_result)

    new_card = await ReportCardService._create_card_from_results(
        db,
        actor,
"""
if old not in text:
    raise RuntimeError("report card historical enrollment test anchor missing")
text = text.replace(old, new, 1)
write(path, text)

# Existing entitlement tests are focused on the method under test; periodic
# stale-checkout reconciliation gets its own regression test.
path = "backend/tests/unit/subscriptions/test_term_entitlements.py"
text = read(path)
fixture = '''\n\n@pytest.fixture(autouse=True)\ndef _isolate_periodic_pending_checkout_cleanup():\n    with patch.object(\n        TermPlanEntitlementService,\n        "expire_stale_pending_checkouts",\n        new=AsyncMock(return_value=0),\n    ):\n        yield\n'''
anchor = "\n\ndef test_free_is_distinct_from_trial_and_does_not_inherit_paid_features() -> None:\n"
if fixture not in text:
    if anchor not in text:
        raise RuntimeError("term entitlement test fixture anchor missing")
    text = text.replace(anchor, fixture + anchor, 1)
write(path, text)

# Real term entitlements always have a persisted id. Keep the precedence unit
# fixture faithful to the ORM entity now that current subscription responses
# expose that canonical entitlement identity.
path = "backend/tests/unit/subscriptions/test_term_subscription_precedence.py"
text = read(path)
old = """    entitlement = SimpleNamespace(
        plan_code=SubscriptionPlan.PROFESSIONAL,
"""
new = """    entitlement = SimpleNamespace(
        id=uuid4(),
        plan_code=SubscriptionPlan.PROFESSIONAL,
"""
if old not in text:
    raise RuntimeError("term entitlement precedence fixture anchor missing")
text = text.replace(old, new, 1)
write(path, text)

# Add direct regression coverage for the service-safe closing guard itself.
path = "backend/tests/unit/test_academic_refactor_regressions.py"
text = read(path)
append = '''\n\n@pytest.mark.asyncio\nasync def test_academic_write_guard_blocks_current_closing_session():\n    from app.core.exceptions import ConflictException\n    from app.modules.student_academics.write_guard import ensure_academic_write_window\n\n    closing = SimpleNamespace(id=uuid.uuid4(), name="2026/2027")\n    result = SimpleNamespace(first=lambda: closing)\n    db = SimpleNamespace(execute=AsyncMock(return_value=result))\n\n    with pytest.raises(ConflictException, match="current session is closing"):\n        await ensure_academic_write_window(db, tenant_id=uuid.uuid4())\n\n\n@pytest.mark.asyncio\nasync def test_academic_write_guard_allows_non_closing_session():\n    from app.modules.student_academics.write_guard import ensure_academic_write_window\n\n    result = SimpleNamespace(first=lambda: None)\n    db = SimpleNamespace(execute=AsyncMock(return_value=result))\n\n    await ensure_academic_write_window(db, tenant_id=uuid.uuid4())\n    db.execute.assert_awaited_once()\n'''
if "test_academic_write_guard_blocks_current_closing_session" not in text:
    text += append
write(path, text)
