from pydantic import BaseModel
from typing import List


class ResolutionDoc(BaseModel):
    doc_id: str
    content: str
    score: float
    metadata: dict


class ScenarioDoc(BaseModel):
    question: str
    answer: str
    legal_interpretation: str
    evidence: str
    situation_type: str


class RAGOutput(BaseModel):
    user_query: str
    situation_type: str
    rewritten_query: str
    resolution_docs: List[ResolutionDoc]
    scenario_docs: List[ScenarioDoc]