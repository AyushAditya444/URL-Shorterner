from datetime import datetime

from pydantic import BaseModel, HttpUrl, field_validator


class LinkCreate(BaseModel):
    url: HttpUrl
    custom_alias: str | None = None
    expires_at: datetime | None = None

    @field_validator("custom_alias")
    @classmethod
    def alias_must_be_slug_like(cls, v):
        if v is not None and (len(v) < 3 or not v.replace("-", "").isalnum()):
            raise ValueError("custom_alias must be at least 3 alphanumeric/hyphen characters")
        return v


class LinkOut(BaseModel):
    id: int
    code: str
    short_url: str
    target_url: str
    is_custom_alias: bool
    expires_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class DailyCount(BaseModel):
    date: str
    count: int


class ReferrerCount(BaseModel):
    referrer: str | None
    count: int


class AnalyticsOut(BaseModel):
    total_clicks: int
    clicks_by_day: list[DailyCount]
    top_referrers: list[ReferrerCount]
