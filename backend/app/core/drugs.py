"""Curated drug library access."""

from __future__ import annotations

import json
from functools import lru_cache

from .config import DATA_DIR


@lru_cache(maxsize=1)
def load_library() -> list[dict]:
    with open(DATA_DIR / "drug_library.json", "r", encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def load_targets() -> list[dict]:
    with open(DATA_DIR / "targets.json", "r", encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def load_evidence() -> dict:
    with open(DATA_DIR / "evidence.json", "r", encoding="utf-8") as fh:
        return json.load(fh)


def search_drugs(query: str = "", limit: int = 50, offset: int = 0) -> tuple[list[dict], int]:
    lib = load_library()
    q = query.strip().lower()
    if q:
        lib = [d for d in lib if q in d["name"].lower()
               or q in (d.get("indication") or "").lower()
               or q in (d.get("drug_class") or "").lower()]
    total = len(lib)
    return lib[offset: offset + limit], total


def library_stats() -> dict:
    lib = load_library()
    classes: dict[str, int] = {}
    repurposed = 0
    for d in lib:
        c = d.get("drug_class") or "Other"
        classes[c] = classes.get(c, 0) + 1
        if d.get("known_repurposing"):
            repurposed += 1
    top_classes = sorted(classes.items(), key=lambda kv: -kv[1])[:8]
    return {"total": len(lib), "classes": top_classes, "with_repurposing_evidence": repurposed}
