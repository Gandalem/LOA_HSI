from __future__ import annotations

from fastapi import APIRouter, Query

from app.models.schemas import CharacterSummary
from app.services.character_parser import build_character_summary
from app.services.lostark_client import LostArkClient
from app.services.class_preset import resolve_class_engraving_preset

router = APIRouter(prefix="/characters", tags=["characters"])


@router.get("/{character_name}/summary", response_model=CharacterSummary)
def get_character_summary(character_name: str, use_cache: bool = Query(True)) -> CharacterSummary:
    bundle, raw_path = LostArkClient().get_character_bundle(character_name, use_cache=use_cache)
    summary = build_character_summary(bundle, raw_saved_path=raw_path)
    summary.class_engraving_preset = resolve_class_engraving_preset(summary, bundle)
    return summary
