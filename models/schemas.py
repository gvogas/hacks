from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class StudyStartRequest(BaseModel):
    topic: str
    session_id: Optional[str] = None


class GenerateLearningRequest(BaseModel):
    session_id: str
    num_flashcards: int = 10
    num_questions: int = 5


class QuizAnswer(BaseModel):
    question_id: int
    selected: str


class QuizSubmitRequest(BaseModel):
    session_id: str
    answers: list[QuizAnswer]


class PlanGenerateRequest(BaseModel):
    session_id: str
    available_days: int = 7
    hours_per_day: float = 2.0
