from fastapi import Depends, HTTPException
from starlette.requests import Request

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "leads":            ["super_admin", "sales", "design"],
    "quotations":       ["super_admin", "sales"],
    "design_files":     ["super_admin", "design"],
    "production_files": ["super_admin", "design"],
    "tasks":            ["super_admin", "sales", "design"],
    "social":           ["super_admin"],
    "activity_log":     ["super_admin"],
    "user_management":  ["super_admin"],
}


def require_permission(feature: str):
    allowed = ROLE_PERMISSIONS[feature]

    def dependency(request: Request):
        if request.session.get("user_role") not in allowed:
            raise HTTPException(status_code=403)

    return Depends(dependency)
