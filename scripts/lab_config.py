"""Validated expectations for the fixed local Docker lab."""
from functools import lru_cache
from ipaddress import IPv4Address, IPv4Network
import os
from pathlib import Path
from typing import Literal
import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config/lab.yaml"
SCENARIOS = ("all", "baseline", "link", "application")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Router(StrictModel):
    peer: IPv4Address
    remote_route: IPv4Network


class Application(StrictModel):
    host: IPv4Address
    port: int = Field(ge=1, le=65535, strict=True)
    endpoint: str
    expected_status: int = Field(ge=200, le=299, strict=True)
    expected_json: dict

    @field_validator("host")
    @classmethod
    def lab_host(cls, value):
        if value not in IPv4Network("10.101.2.0/24"):
            raise ValueError("Application must be in the dedicated lab server subnet")
        return value

    @field_validator("endpoint")
    @classmethod
    def safe_path(cls, value):
        if not value.startswith("/") or value.startswith("//") or any(c.isspace() for c in value):
            raise ValueError("Use an absolute HTTP path without whitespace")
        return value

    @property
    def url(self):
        return f"http://{self.host}:{self.port}{self.endpoint}"


class Timeouts(StrictModel):
    request_seconds: int = Field(ge=1, le=10, strict=True)
    recovery_seconds: int = Field(ge=10, le=300, strict=True)


class LabConfig(StrictModel):
    scenario: Literal["all", "baseline", "link", "application"] = "all"
    routers: dict[Literal["r1", "r2"], Router]
    application: Application
    expected_hops: list[IPv4Address] = Field(min_length=3, max_length=3)
    timeouts: Timeouts

    @model_validator(mode="after")
    def complete_topology(self):
        if set(self.routers) != {"r1", "r2"}:
            raise ValueError("Both r1 and r2 expectations are required")
        if self.expected_hops[-1] != self.application.host:
            raise ValueError("Last expected hop must match the application host")
        return self


def load_config(path=DEFAULT_CONFIG, scenario=None):
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Configuration must be a YAML mapping")
        if scenario is not None:
            raw["scenario"] = scenario
        return LabConfig.model_validate(raw)
    except (OSError, yaml.YAMLError) as error:
        raise ValueError("Cannot read the YAML configuration") from error


@lru_cache(maxsize=1)
def current_config():
    return load_config(os.environ.get("NETAPP_CONFIG", str(DEFAULT_CONFIG)), os.environ.get("NETAPP_SCENARIO"))
