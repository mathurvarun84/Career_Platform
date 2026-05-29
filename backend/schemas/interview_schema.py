"""Pydantic request/response models for the interview endpoints."""

from pydantic import BaseModel


class StartInterviewRequest(BaseModel):
    resume_text: str
    company: str
    seniority: str
    question_mode: str = "mixed"


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
