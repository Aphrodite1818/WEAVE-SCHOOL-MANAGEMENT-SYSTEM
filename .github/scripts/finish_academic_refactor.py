from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text()


def write(path: str, value: str) -> None:
    Path(path).write_text(value)


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one match, found {count}: {old[:120]!r}")
    write(path, text.replace(old, new, 1))


# ---------------------------------------------------------------------------
# Subscription lifecycle: stale Paystack checkouts must expire without a new
# checkout request, and current subscription must reflect the effective term
# entitlement instead of returning null for a paid term.
# ---------------------------------------------------------------------------
path = "backend/app/modules/subscriptions/term_entitlement_service.py"
text = read(path)
anchor = """    @staticmethod
    def amount_kobo(plan: SubscriptionPlan) -> int:
"""
helper = """    @staticmethod
    def _pending_checkout_is_stale(
        transaction: PaymentTransaction,
        *,
        as_of: datetime | None = None,
    ) -> bool:
        now = as_of or datetime.now(timezone.utc)
        return (
            transaction.status == PaymentStatus.PENDING
            and transaction.created_at is not None
            and transaction.created_at < now - PENDING_CHECKOUT_TTL
        )

    @staticmethod
    async def expire_stale_pending_checkouts(
        db: AsyncSession,
        *,
        as_of: datetime | None = None,
        tenant_id: uuid.UUID | None = None,
        term_id: uuid.UUID | None = None,
    ) -> int:
        now = as_of or datetime.now(timezone.utc)
        query = select(PaymentTransaction).where(
            PaymentTransaction.provider == PaymentProvider.PAYSTACK,
            PaymentTransaction.status == PaymentStatus.PENDING,
            PaymentTransaction.created_at < now - PENDING_CHECKOUT_TTL,
        )
        if tenant_id is not None:
            query = query.where(PaymentTransaction.tenant_id == tenant_id)
        if term_id is not None:
            query = query.where(PaymentTransaction.academic_term_id == term_id)
        rows = list((await db.execute(query.with_for_update())).scalars().all())
        for transaction in rows:
            transaction.status = PaymentStatus.ABANDONED
            transaction.failure_reason = "Pending checkout expired before payment completion."
        if rows:
            await db.flush()
        return len(rows)

"""
if helper not in text:
    if anchor not in text:
        raise RuntimeError("term entitlement helper anchor missing")
    text = text.replace(anchor, helper + anchor, 1)
old = """        pending = await TermPlanEntitlementService._get_pending_checkout(
            db, tenant_id, term_id, lock=True
        )
        if pending is not None:
            raise ConflictException(
                "This academic term still has a pending Paystack checkout. "
                "Complete the payment or wait for the checkout to expire before finalizing closure."
            )
"""
new = """        await TermPlanEntitlementService.expire_stale_pending_checkouts(
            db,
            tenant_id=tenant_id,
            term_id=term_id,
        )
        pending = await TermPlanEntitlementService._get_pending_checkout(
            db, tenant_id, term_id, lock=True
        )
        if pending is not None:
            raise ConflictException(
                "This academic term still has an active Paystack checkout. "
                "Complete the payment or wait for the checkout to expire before finalizing closure."
            )
"""
if old not in text:
    raise RuntimeError("close_for_term pending checkout anchor missing")
text = text.replace(old, new, 1)
old = """        now = as_of or datetime.now(timezone.utc)
        result = await db.execute(
"""
new = """        now = as_of or datetime.now(timezone.utc)
        abandoned_checkouts = await TermPlanEntitlementService.expire_stale_pending_checkouts(
            db,
            as_of=now,
        )
        result = await db.execute(
"""
if old not in text:
    raise RuntimeError("term reconciliation anchor missing")
text = text.replace(old, new, 1)
old = '        return {"closed_term_repaired": repaired_closed, "safety_expired": safety_expired}\n'
new = """        return {
            "closed_term_repaired": repaired_closed,
            "safety_expired": safety_expired,
            "pending_checkouts_abandoned": abandoned_checkouts,
        }
"""
if old not in text:
    raise RuntimeError("term reconciliation result anchor missing")
text = text.replace(old, new, 1)
write(path, text)

path = "backend/app/modules/subscriptions/service.py"
text = read(path)
old = """    subscription: TenantSubscription | None = None
"""
new = """    subscription: TenantSubscription | None = None
    effective_entitlement_id: uuid.UUID | None = None
"""
if old not in text:
    raise RuntimeError("resolved subscription state anchor missing")
text = text.replace(old, new, 1)
old = """                    provider=entitlement.provider,
                )
"""
new = """                    provider=entitlement.provider,
                    effective_entitlement_id=entitlement.id,
                )
"""
if old not in text:
    raise RuntimeError("term entitlement resolution anchor missing")
text = text.replace(old, new, 1)
old = """        if state.subscription is None:
            return None
        return TenantSubscriptionResponse.model_validate(
            {
                "id": state.subscription.id,
                "tenant_id": state.tenant_id,
                "plan_code": normalize_plan_code(state.subscription.plan_code),
                "status": state.status,
                "billing_interval": state.billing_interval,
                "trial_ends_at": state.trial_ends_at,
                "provider": state.provider or PaymentProvider.MANUAL,
            }
        )
"""
new = """        effective_id = (
            state.subscription.id
            if state.subscription is not None
            else state.effective_entitlement_id
        )
        if effective_id is None:
            return None
        plan_code = (
            normalize_plan_code(state.subscription.plan_code)
            if state.subscription is not None
            else state.plan_code
        )
        return TenantSubscriptionResponse.model_validate(
            {
                "id": effective_id,
                "tenant_id": state.tenant_id,
                "plan_code": plan_code,
                "status": state.status,
                "billing_interval": state.billing_interval,
                "trial_ends_at": state.trial_ends_at,
                "provider": state.provider or PaymentProvider.MANUAL,
            }
        )
"""
if old not in text:
    raise RuntimeError("subscription response anchor missing")
text = text.replace(old, new, 1)
write(path, text)

# ---------------------------------------------------------------------------
# Frontend checkout must never guess which draft term is being purchased.
# Explicit draft term context is required; only the uniquely current OPEN or
# CLOSING term may be inferred safely.
# ---------------------------------------------------------------------------
path = "frontend/src/services/subscriptionService.js"
text = read(path)
text = text.replace("""const TERM_ORDER = {
  first_term: 1,
  second_term: 2,
  third_term: 3,
};

""", "", 1)
start = text.index("const resolveCheckoutTermId = async (explicitTermId) => {")
end = text.index("\n};\n\nexport const subscriptionService", start) + len("\n};")
replacement = """const resolveCheckoutTermId = async (explicitTermId) => {
  if (explicitTermId) return explicitTermId;

  const response = await api.get(
    "/tenant-admin/academics/terms?limit=100&is_current=true",
  );
  const terms = response?.items || response || [];
  const currentTerms = terms.filter(
    (item) => item.is_current && ["open", "closing"].includes(item.status),
  );
  if (currentTerms.length === 1 && currentTerms[0]?.id) {
    return currentTerms[0].id;
  }
  if (currentTerms.length > 1) {
    throw new Error(
      "Academic term state is inconsistent. Resolve the current term before purchasing a plan.",
    );
  }
  throw new Error(
    "Select the academic term you want to purchase before starting checkout.",
  );
};"""
text = text[:start] + replacement + text[end:]
write(path, text)

# ---------------------------------------------------------------------------
# Student dashboard response alignment. The dashboard already fetched the
# student profile before this bundle; the duplicate getMyStudent call shifted
# every Promise.all response by one slot and could surface stale/incorrect UI.
# ---------------------------------------------------------------------------
path = "frontend/src/pages/student/StudentDashboardPage.jsx"
text = read(path)
old = """          ] = await Promise.all([
            studentService.getMyStudent({ signal: controller.signal }),
            studentService.getMyParentLinks({ signal: controller.signal }),
"""
new = """          ] = await Promise.all([
            studentService.getMyParentLinks({ signal: controller.signal }),
"""
if old not in text:
    raise RuntimeError("student dashboard Promise.all alignment anchor missing")
text = text.replace(old, new, 1)
write(path, text)

# Load all classes supported by the backend contract for assignment selectors;
# assignments themselves remain paginated.
path = "frontend/src/features/academic-admin/TeacherAssignmentsWorkspace.jsx"
text = read(path)
text = text.replace(
    "classService.getClasses({ limit: 100, activeOnly: true })",
    "classService.getClasses({ limit: 500, activeOnly: true })",
    1,
)
write(path, text)

# ---------------------------------------------------------------------------
# Backend regression coverage.
# ---------------------------------------------------------------------------
path = "backend/tests/test_academic_refactor_regressions.py"
text = read(path)
append = '''\n\ndef test_pending_checkout_staleness_boundary():\n    from datetime import datetime, timedelta, timezone\n    from types import SimpleNamespace\n\n    from app.modules.subscriptions.subscription_enums import PaymentStatus\n    from app.modules.subscriptions.term_entitlement_service import (\n        PENDING_CHECKOUT_TTL,\n        TermPlanEntitlementService,\n    )\n\n    now = datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)\n    fresh = SimpleNamespace(\n        status=PaymentStatus.PENDING,\n        created_at=now - PENDING_CHECKOUT_TTL + timedelta(seconds=1),\n    )\n    stale = SimpleNamespace(\n        status=PaymentStatus.PENDING,\n        created_at=now - PENDING_CHECKOUT_TTL - timedelta(seconds=1),\n    )\n    assert not TermPlanEntitlementService._pending_checkout_is_stale(fresh, as_of=now)\n    assert TermPlanEntitlementService._pending_checkout_is_stale(stale, as_of=now)\n\n\ndef test_subscription_state_tracks_effective_term_entitlement_identity():\n    from app.modules.subscriptions.service import ResolvedSubscriptionState\n    from app.modules.subscriptions.subscription_enums import (\n        BillingInterval,\n        PaymentProvider,\n        SubscriptionStatus,\n    )\n\n    entitlement_id = uuid.uuid4()\n    state = ResolvedSubscriptionState(\n        tenant_id=uuid.uuid4(),\n        plan_code="plus",\n        status=SubscriptionStatus.ACTIVE,\n        billing_interval=BillingInterval.TERM,\n        provider=PaymentProvider.PAYSTACK,\n        effective_entitlement_id=entitlement_id,\n    )\n    from app.modules.subscriptions.service import SubscriptionFeatureService\n\n    response = SubscriptionFeatureService._state_to_subscription_response(state)\n    assert response is not None\n    assert response.id == entitlement_id\n    assert response.plan_code == "plus"\n'''
if "test_pending_checkout_staleness_boundary" not in text:
    text += append
write(path, text)

# Frontend contract tests use Node's built-in test runner used by this repo.
Path("frontend/test/unit/academic-refactor-contracts.test.js").write_text(r'''import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = async (path) => readFile(new URL(`../../${path}`, import.meta.url), "utf8");

test("student dashboard keeps Promise.all responses aligned", async () => {
  const source = await read("src/pages/student/StudentDashboardPage.jsx");
  const bundleStart = source.indexOf("const bundle = await getCachedDashboardBundle");
  const bundleEnd = source.indexOf("if (!mounted || controller.signal.aborted) return;", bundleStart);
  const bundle = source.slice(bundleStart, bundleEnd);

  assert.equal((bundle.match(/studentService\.getMyStudent/g) || []).length, 0);
  assert.equal((bundle.match(/studentService\.getMyParentLinks/g) || []).length, 1);
  assert.equal((bundle.match(/studentService\.getMyParentLinkRequests/g) || []).length, 1);
  assert.equal((bundle.match(/dashboardService\.getStudentAnalytics/g) || []).length, 1);
  assert.equal((bundle.match(/academicService\.listMyResults/g) || []).length, 1);
  assert.equal((bundle.match(/reportCardService\.listMyReportCards/g) || []).length, 1);
  assert.equal((bundle.match(/academicService\.listMySubjectCards/g) || []).length, 1);
});

test("term checkout never guesses the first draft term", async () => {
  const source = await read("src/services/subscriptionService.js");
  assert.doesNotMatch(source, /TERM_ORDER/);
  assert.doesNotMatch(source, /draftTerms\[0\]/);
  assert.match(source, /Select the academic term you want to purchase/);
  assert.match(source, /\["open", "closing"\]\.includes\(item\.status\)/);
});

test("teacher assignment class selector uses the backend 500-class contract", async () => {
  const source = await read("src/features/academic-admin/TeacherAssignmentsWorkspace.jsx");
  assert.match(source, /getClasses\(\{ limit: 500, activeOnly: true \}\)/);
});
''')
