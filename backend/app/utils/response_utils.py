from typing import Optional

from fastapi import HTTPException


def api_error(status_code: int, code: str, message: str, details: Optional[dict] = None) -> HTTPException:
    detail = {"code": code, "message": message}
    if details:
        detail["details"] = details
    return HTTPException(status_code=status_code, detail=detail)