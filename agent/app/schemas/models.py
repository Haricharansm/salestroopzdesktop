from typing import Any, Dict, Union
from pydantic import BaseModel, field_validator

class LaunchRequest(BaseModel):
    company_name: str | None = None
    offering: Union[str, Dict[str, Any]]
    icp: Union[str, Dict[str, Any]]

    @field_validator("offering", mode="before")
    def normalize_offering(cls, v):
        if isinstance(v, str):
            return {"text": v}
        return v

    @field_validator("icp", mode="before")
    def normalize_icp(cls, v):
        if isinstance(v, str):
            return {"text": v}
        return v
