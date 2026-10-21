from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SlideDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["cover", "content", "closing"]
    title: str = Field(min_length=1, max_length=100)
    bullets: list[str] = Field(default_factory=list, max_length=5)


class PptOutline(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slides: list[SlideDraft] = Field(min_length=6, max_length=20)