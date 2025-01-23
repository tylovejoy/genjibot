from __future__ import annotations

import msgspec


class MapSubmissionBody(msgspec.Struct):
    map_code: str
    map_type: str
    map_name: str
    difficulty: str
    checkpoints: int
    creator_id: int
    nickname: str
    description: str | None = None
    mechanics: list[str] | None = None
    restrictions: list[str] | None = None
    guides: list[str] | None = None
    gold: float | None = None
    silver: float | None = None
    bronze: float | None = None

    rabbit_data: dict | None = None


class BulkArchiveMapBody(msgspec.Struct):
    map_code: str

    rabbit_data: dict | None = None
