from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class NightOutRequest(BaseModel):
	city: str
	vibe: str
	date: str
	group_size: int = 4
	notes: str = ""


class Stop(BaseModel):
	model_config = {"coerce_numbers_to_str": True}

	time: str = Field(description="When to arrive, e.g. '22:00'")
	name: str = Field(description="Venue or spot name")
	category: str = Field(description="club | rave | afterhours | food | pregame | other")
	vibe: str = Field(default="", description="One-line vibe description")
	address: str = Field(default="", description="Address if known")
	cost: str = Field(default="", description="Estimated cost per person")
	tips: str = Field(default="", description="Door policy, dress code, or other tips")
	degen_score: int = Field(default=5, ge=0, le=10, description="0=sober, 10=absolutely unhinged")

	@field_validator("degen_score", mode="before")
	@classmethod
	def coerce_degen_score(cls, v: object) -> int:
		if isinstance(v, float):
			return int(round(v))
		return v


class Itinerary(BaseModel):
	city: str
	date: str
	vibe: str
	group_size: int
	stops: list[Stop] = Field(default_factory=list)
	total_estimated_cost: str = ""
	survival_tips: str = ""
