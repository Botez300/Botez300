"""Scan definition schema. A scan is data: it can be stored, shown to the user and replayed."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Timeframe = Literal["1D", "1W", "1M"]
Comparator = Literal[">", ">=", "<", "<=", "crosses_above", "crosses_below"]
PriceField = Literal["open", "high", "low", "close", "volume"]


class Operand(BaseModel):
    """A number, a price field, or an indicator output — read `offset` completed bars back."""

    model_config = ConfigDict(extra="forbid")

    value: float | None = None
    field: PriceField | None = None
    indicator: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    output: str | None = None  # defaults to the indicator's first output
    timeframe: Timeframe = "1D"
    offset: int = Field(0, ge=0, le=500)
    multiplier: float = Field(1.0, gt=0, le=1000)

    @model_validator(mode="after")
    def _one_kind(self) -> Operand:
        if sum(x is not None for x in (self.value, self.field, self.indicator)) != 1:
            raise ValueError("operand needs exactly one of: value, field, indicator")
        return self

    def label(self) -> str:
        if self.value is not None:
            return f"{self.value:g}"
        if self.field:
            base: str = self.field
        else:
            args = ",".join(f"{v:g}" if isinstance(v, (int, float)) else str(v) for v in self.params.values())
            base = f"{self.indicator}({args})" + (f".{self.output}" if self.output else "")
        if self.multiplier != 1.0:
            base = f"{self.multiplier:g}×{base}"
        if self.offset:
            base += f"[{self.offset}]"
        return f"{base} {self.timeframe}"


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    left: Operand
    op: Comparator
    right: Operand

    def label(self) -> str:
        return f"{self.left.label()} {self.op.replace('_', ' ')} {self.right.label()}"


class Group(BaseModel):
    model_config = ConfigDict(extra="forbid")
    logic: Literal["and", "or"] = "and"
    rules: list[Annotated[Condition | Group, Field()]] = Field(min_length=1, max_length=25)

    def conditions(self) -> list[Condition]:
        out: list[Condition] = []
        for r in self.rules:
            out.extend(r.conditions() if isinstance(r, Group) else [r])
        return out

    def depth(self) -> int:
        return 1 + max((r.depth() for r in self.rules if isinstance(r, Group)), default=0)

    @model_validator(mode="after")
    def _limits(self) -> Group:
        if self.depth() > 4:
            raise ValueError("condition groups may be nested at most 4 levels deep")
        return self


class ScanDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filter: Group
    sort_by: Operand | None = None
    sort_desc: bool = True
    limit: int = Field(50, ge=1, le=500)


Group.model_rebuild()
