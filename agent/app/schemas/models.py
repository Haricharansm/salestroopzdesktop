from pydantic import BaseModel
from typing import Any, Dict, Optional, Union

class WorkspaceRequest(BaseModel):
    company_name: str
    offering: str
    icp: str

class AgentLaunchRequest(BaseModel):
    offering: Union[str, Dict[str, Any]]
    icp: Union[str, Dict[str, Any]]
    workspace_id: Optional[str] = None
