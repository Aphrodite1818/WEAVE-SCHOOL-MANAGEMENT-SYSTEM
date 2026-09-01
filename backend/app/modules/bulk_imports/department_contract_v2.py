"""Install the canonical v2 student hierarchy resolver for every import path."""

from app.modules.bulk_imports.optimized_validation import resolve_student_class_references_batch
from app.modules.bulk_imports.service import BulkImportService


# Direct imports are disabled in the product flow, but keep the service's public
# implementation aligned with dry-run validation so no internal caller can fall
# back to the removed level-owned Department contract.
BulkImportService.resolve_student_class_references = staticmethod(
    resolve_student_class_references_batch
)
