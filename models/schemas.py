from typing import Annotated, Literal, Optional

from pydantic import BaseModel, EmailStr, Field, StringConstraints

SessionId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
TopicText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
QuizChoice = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1, pattern=r"^[A-Da-d]?$")]


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class StudyStartRequest(BaseModel):
    topic: Optional[TopicText] = None
    session_id: Optional[SessionId] = None
    source: Literal['both', 'web', 'files'] = 'both'


class GenerateLearningRequest(BaseModel):
    session_id: SessionId
    num_flashcards: int = Field(default=10, ge=1, le=30)
    num_questions: int = Field(default=5, ge=1, le=20)
    difficulty: str = Field(default="intermediate", pattern=r"^(beginner|intermediate|advanced)$")


class QuizAnswer(BaseModel):
    question_id: int = Field(ge=0)
    selected: QuizChoice = ""


class QuizSubmitRequest(BaseModel):
    session_id: SessionId
    answers: list[QuizAnswer] = Field(min_length=1, max_length=100)


class PlanGenerateRequest(BaseModel):
    session_id: SessionId
    available_days: int = Field(default=7, ge=1, le=30)
    hours_per_day: float = Field(default=2.0, ge=0.5, le=12.0)


class StudyTickRequest(BaseModel):
    elapsed_seconds: int = Field(ge=1, le=900)


class PurchaseUpgradeRequest(BaseModel):
    upgrade_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class SpotifyPlayRequest(BaseModel):
    context_uri: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]] = None
    uris: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]] = Field(
        default_factory=list,
        max_length=50,
    )
    device_id: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]] = None


class SpotifyTransferRequest(BaseModel):
    device_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    play: bool = False
