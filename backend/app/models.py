"""
Central Registry for SQLAlchemy ORM Models.

This module imports every SQLAlchemy mapped class in the application exactly once.
It ensures that models are registered properly for mapper configuration in seeders,
standalone scripts, Alembic migrations, and tests.
"""

# Tenant Management
import app.tenant_management.models

# Modules
import app.modules.announcements.models
import app.modules.attendance.models
import app.modules.auth.models
import app.modules.auth_identity.models
import app.modules.bulk_imports.models
import app.modules.classes.models
import app.modules.email_outbox.models
import app.modules.finance.models
import app.modules.media.models
import app.modules.parents.models
import app.modules.report_cards.models
import app.modules.results.models
import app.modules.students.models
import app.modules.student_academics.models
import app.modules.subjects.models
import app.modules.subscriptions.models
import app.modules.superadmin.models
import app.modules.teachers.models
import app.modules.tenant_admins.models
import app.modules.tenant_branding.models
