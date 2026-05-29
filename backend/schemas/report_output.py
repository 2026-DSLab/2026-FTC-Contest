from pydantic import BaseModel
from typing import List


class ChecklistItem(BaseModel):
    priority: str  # 필수 / 권장
    content: str


class AgentReport(BaseModel):
    agent_type: str  # law / resolution / precedent / case
    content: str
    confidence_score: float  # 1~100


class ReportOutput(BaseModel):
    risk_score: float          # 0~100
    risk_level: str            # 맑음 / 흐림 / 비
    summary: str
    agent_reports: List[AgentReport]
    checklist: List[ChecklistItem]
