"""Tripwire DSL. FROZEN pre-registered experimental material. Do not edit."""
from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class Scope(str, Enum):
    GLOBAL = "global"
    LOCAL = "local"


class Category(str, Enum):
    API_SURFACE = "API_SURFACE"
    SCHEMA_DRIFT = "SCHEMA_DRIFT"
    PERMISSION_AUTH = "PERMISSION_AUTH"
    RETRIEVAL_INTEGRITY = "RETRIEVAL_INTEGRITY"
    TOOL_CONTRACT = "TOOL_CONTRACT"


class Signal(BaseModel):
    type: Literal["http_response", "tool_output", "retrieval_content", "auth_state"]
    method: Optional[str] = None
    url_pattern: Optional[str] = None          # glob over world-server paths
    status_in: Optional[list[int]] = None
    field_absent: Optional[str] = None          # JSON pointer expected but missing
    field_regex: Optional[dict[str, str]] = None  # {json_pointer: regex}
    contradicts_assumption: Optional[str] = None  # assumption id, for retrieval checks
    order_violation: Optional[dict[str, str]] = None  # {"required_before": tool, "observed": tool}

    @model_validator(mode="after")
    def at_least_one_predicate(self):
        preds = [self.status_in, self.field_absent, self.field_regex,
                 self.contradicts_assumption, self.order_violation]
        if not any(p is not None for p in preds):
            raise ValueError("signal must contain at least one predicate")
        return self


class Action(BaseModel):
    on_trigger: Literal["PAUSE_AND_REPLAN", "ESCALATE_TO_SENTINEL", "LOG"]
    hint: str = Field(min_length=8)


class Tripwire(BaseModel):
    id: str = Field(pattern=r"^tw_[a-z0-9_]+$")
    severity: Severity
    scope: Scope
    subplan_id: Optional[str] = None            # required iff scope == local
    assumption: str = Field(min_length=12)
    assumption_id: str
    category_weights: dict[Category, float]
    signal: Signal
    action: Action
    evidence_fields: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def checks(self):
        s = sum(self.category_weights.values())
        if not (0.99 <= s <= 1.01):
            raise ValueError("category_weights must sum to 1.0")
        if self.scope == Scope.LOCAL and not self.subplan_id:
            raise ValueError("local scope requires subplan_id")
        return self


class TripwireSet(BaseModel):
    plan_id: str
    tripwires: list[Tripwire] = Field(min_length=1, max_length=12)
