from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
Office = Literal["president","senate","house","governor","state_house","state_senate"]
Geography = Literal["country","state","county","precinct","congressional_district","state_legislative_district","other_reporting_unit"]
ResultStatus = Literal["preliminary","certified","estimated","historical_final"]
class ElectionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    election_year: int = Field(ge=1788, le=2200)
    election_type: str = Field(min_length=3)
    office: Office
    geography_type: Geography
    geography_id: str = Field(min_length=1)
    geography_name: str = Field(min_length=1)
    state_fips: str | None = None
    district: str | None = None
    candidate: str = Field(min_length=1)
    party: str | None = None
    votes: int = Field(ge=0)
    total_votes: int | None = Field(default=None, ge=0)
    result_status: ResultStatus
    source_id: str = Field(min_length=3)
    source_url: str | None = None
    source_published_at: str | None = None
    extracted_at: str
    @field_validator("state_fips")
    @classmethod
    def valid_fips(cls, value):
        if value is not None and (not value.isdigit() or len(value) != 2):
            raise ValueError("state_fips must be a two-digit FIPS code")
        return value
    @field_validator("total_votes")
    @classmethod
    def total_not_below_candidate(cls, value, info):
        votes = info.data.get("votes")
        if value is not None and votes is not None and value < votes:
            raise ValueError("total_votes cannot be below candidate votes")
        return value
