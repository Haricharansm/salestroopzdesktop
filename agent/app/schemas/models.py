from typing import Any, Dict, Union, Optional
from pydantic import BaseModel, field_validator

TextLike = Union[str, Dict[str, Any]]

def coerce_text(v: Any) -> str:
    """
    Accept:
      - "hello"
      - {"text": "hello"}
      - {"value": "hello"}
      - {"input": "hello"}
    Return canonical string.
    """
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, dict):
        for key in ("text", "value", "input", "content"):
            if key in v and isinstance(v[key], str):
                return v[key].strip()
        # last-resort: if dict has a single string value, take it
        for _, val in v.items():
            if isinstance(val, str):
                return val.strip()
    # if we reach here, it's an unsupported shape
    raise ValueError("Expected a string or an object containing a text field")

class WorkspaceRequest(BaseModel):
    company_name: str = ""
    offering: TextLike
    icp: TextLike

    @field_validator("offering", "icp", mode="before")
    @classmethod
    def _normalize_text_fields(cls, v: Any) -> str:
        return coerce_text(v)

class LaunchRequest(BaseModel):
    offering: TextLike
    icp: TextLike
    workspace_id: Optional[int] = None

    @field_validator("offering", "icp", mode="before")
    @classmethod
    def _normalize_text_fields(cls, v: Any) -> str:
        return coerce_text(v)
