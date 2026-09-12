"""Hub cities and known first-party stores."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from .config import DATA_DIR


@dataclass
class Hub:
    id: str
    city: str
    country: str
    lat: float
    lon: float
    languages: list[str]
    priority: int = 2
    areas: list[str] = field(default_factory=list)


@dataclass
class Store:
    domain: str
    name: str
    country: str


@lru_cache
def load_hubs(path: Path | None = None) -> tuple[list[Hub], list[Store]]:
    raw = yaml.safe_load((path or DATA_DIR / "hubs.yaml").read_text())
    hubs = [Hub(**h) for h in raw["hubs"]]
    stores = [Store(**s) for s in raw.get("shopify_stores", [])]
    return hubs, stores


def hubs(max_priority: int = 3) -> list[Hub]:
    return [h for h in load_hubs()[0] if h.priority <= max_priority]


def stores() -> list[Store]:
    return load_hubs()[1]


def hub_by_id(hub_id: str) -> Hub:
    for h in load_hubs()[0]:
        if h.id == hub_id:
            return h
    raise KeyError(hub_id)
