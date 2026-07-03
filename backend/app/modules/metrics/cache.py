#==========================#
#      cache metric.py     #
#==========================#

"""This file is responsible for caching frequently used data from the metric service"""



from __future__ import annotations
from uuid import UUID 
from app.core.cache.base import build_cache_key , global_prefix , tenant_prefix



def superadmin_dashboard_cache_key() -> str:
    """
    Cache Key for the global superadmin dashboard metrics.

    Output:
    global : dashboard : superadmin : metrics
    """
    return build_cache_key(
        global_prefix(),
        "dashboard",
        "superadmin",
        "metrics"
    )



def tenant_admin_dashboard_cache_key(tenant_id : UUID) -> str:
    """
    Cache key for one tenant admin dashboard 

    Output:
    tenant:{tenant_id}:dashboard:tenant-admin:metrics
    """
    return build_cache_key(
        tenant_prefix(str(tenant_id)),
        "dashboard",
        "tenant-admin",
        "metrics"
    )



def teacher_dashboard_cache_key(tenant_id : UUID , teacher_id : UUID):
    """
    Cache key for one teacher dashboard.

    Output:
    tenant:{tenant_id}:dashboard:teacher:{teacher_id}:metrics
    """
    return build_cache_key(
        tenant_prefix(str(tenant_id)),
        "dashboard",
        "teacher",
        str(teacher_id),
        "metrics",
    )



def parent_dashboard_cache_key(tenant_id: UUID, parent_id: UUID) -> str:
    """
    Cache key for one parent dashboard.

    Output:
    tenant:{tenant_id}:dashboard:parent:{parent_id}:metrics
    """
    return build_cache_key(
        tenant_prefix(str(tenant_id)),
        "dashboard",
        "parent",
        str(parent_id),
        "metrics",
    )


def student_dashboard_cache_key(tenant_id: UUID, student_id: UUID) -> str:
    """
    Cache key for one student dashboard.

    Output:
    tenant:{tenant_id}:dashboard:student:{student_id}:metrics
    """
    return build_cache_key(
        tenant_prefix(str(tenant_id)),
        "dashboard",
        "student",
        str(student_id),
        "metrics",
    )