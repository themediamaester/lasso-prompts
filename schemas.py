"""Typed Phase 1 business profile with traceable website evidence."""
from pydantic import BaseModel, Field
from typing import Literal

class Finding(BaseModel):
    value: str = Field(min_length=1, max_length=600)
    source_url: str
    evidence: str = Field(min_length=1, max_length=900)
    confidence: Literal["high", "medium", "low"] = "low"

class Service(BaseModel):
    name: str
    description: str = ""
    source_url: str
    evidence: str
    confidence: Literal["high", "medium", "low"] = "low"

class BusinessProfile(BaseModel):
    name: str
    website: str
    description: str = ""
    business_type: str = ""
    services: list[Service] = Field(default_factory=list)
    audiences: list[Finding] = Field(default_factory=list)
    markets: list[Finding] = Field(default_factory=list)
    problems_solved: list[Finding] = Field(default_factory=list)
    differentiators: list[Finding] = Field(default_factory=list)
    proof_points: list[Finding] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    analyzed_urls: list[str] = Field(default_factory=list)
