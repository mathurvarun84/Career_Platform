"""Pydantic request/response models for the interview endpoints."""

from pydantic import BaseModel


class StartInterviewRequest(BaseModel):
    resume_text: str
    company: str
    seniority: str
    question_mode: str = "mixed"
    run_id: str | None = None
    resume_id: str | None = None


class StartInterviewResponse(BaseModel):
    session_id: str
    questions: list[dict]


class InterviewQuestionsRequest(BaseModel):
    resume_text: str
    company: str
    seniority: str
    question_mode: str = "mixed"


class InterviewQuestionsResponse(BaseModel):
    questions: list[dict]
