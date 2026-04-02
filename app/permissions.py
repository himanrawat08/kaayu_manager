from fastapi import Depends, HTTPException
from starlette.requests import Request

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "contacts":         ["super_admin", "admin", "sales", "design", "viewer"],
    "leads":            ["super_admin", "sales", "design", "viewer"],
    "quotations":       ["super_admin", "sales", "viewer"],
    "design_files":     ["super_admin", "design", "viewer"],
    "production_files": ["super_admin", "design", "viewer", "supervisor"],
    "tasks":            ["super_admin", "sales", "design", "viewer"],
    "social":           ["super_admin", "viewer"],
    "activity_log":     ["super_admin", "viewer"],
    "user_management":  ["super_admin"],
    "job_cards":        ["super_admin"],
}


def require_permission(feature: str):
    allowed = ROLE_PERMISSIONS[feature]

    def dependency(request: Request):
        if request.session.get("user_role") not in allowed:
            raise HTTPException(status_code=403)

    return Depends(dependency)
