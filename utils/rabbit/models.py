from __future__ import annotations

import msgspec


class MapSubmissionBody(msgspec.Struct):
    map_code: str
    map_type: str
    map_name: str
    difficulty: str
    checkpoints: int
    creator_id: int
    mechanics: list[str] | None = None
    restrictions: list[str] | None = None
    description: str | None = None
    guide: str | None = None
    gold: float | None = None
    silver: float | None = None
    bronze: float | None = None
