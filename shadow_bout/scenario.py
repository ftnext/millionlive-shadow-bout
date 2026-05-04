import json
from dataclasses import dataclass
from pathlib import Path

from shadow_bout.models import Janken

_VALID_WILDCARD_VALUES = {"rock", "scissors", "paper"}
_ROUND_FIELDS = ("player_card", "npc_card", "player_wildcard", "npc_wildcard")


@dataclass(frozen=True)
class ScenarioRound:
    player_card_id: str | None = None
    player_wildcard: Janken | None = None
    npc_card_id: str | None = None
    npc_wildcard: Janken | None = None


@dataclass(frozen=True)
class Scenario:
    player_hand_required: tuple[str, ...] = ()
    npc_hand_required: tuple[str, ...] = ()
    rounds: tuple[ScenarioRound | None, ...] = ()


def load_scenario(path: Path, deck_card_ids: list[str]) -> Scenario:
    """シナリオ JSON を読み込み、deck_card_ids に対する妥当性検証をして返す。"""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("scenario root must be an object")

    deck_id_set = set(deck_card_ids)

    player_hand = _validate_required_hand(
        raw.get("player_hand", []), deck_id_set, "player_hand"
    )
    npc_hand = _validate_required_hand(raw.get("npc_hand", []), deck_id_set, "npc_hand")

    rounds_raw = raw.get("rounds", [])
    if not isinstance(rounds_raw, list):
        raise ValueError("rounds must be a list")
    if len(rounds_raw) > 4:
        raise ValueError("rounds must contain at most 4 entries")

    rounds: list[ScenarioRound | None] = []
    for index, entry in enumerate(rounds_raw):
        rounds.append(_validate_round_entry(entry, index, deck_id_set))

    return Scenario(
        player_hand_required=tuple(player_hand),
        npc_hand_required=tuple(npc_hand),
        rounds=tuple(rounds),
    )


def _validate_required_hand(raw, deck_id_set: set[str], field_name: str) -> list[str]:
    if not isinstance(raw, list):
        raise ValueError(f"{field_name} must be a list of card ids")
    if len(raw) > 5:
        raise ValueError(f"{field_name} must have at most 5 entries")
    if len(set(raw)) != len(raw):
        raise ValueError(f"{field_name} must not contain duplicates")
    for card_id in raw:
        if not isinstance(card_id, str):
            raise ValueError(f"{field_name} entries must be strings")
        if card_id not in deck_id_set:
            raise ValueError(f"{field_name} contains unknown card id: {card_id}")
    return list(raw)


def _validate_round_entry(
    entry, index: int, deck_id_set: set[str]
) -> ScenarioRound | None:
    if entry is None:
        return None
    if not isinstance(entry, dict):
        raise ValueError(f"rounds[{index}] must be an object or null")

    unknown_keys = set(entry) - set(_ROUND_FIELDS)
    if unknown_keys:
        raise ValueError(f"rounds[{index}] has unknown keys: {sorted(unknown_keys)}")

    if not any(entry.get(field) is not None for field in _ROUND_FIELDS):
        raise ValueError(
            f"rounds[{index}] must specify at least one field "
            f"(empty objects are not allowed; use null instead)"
        )

    return ScenarioRound(
        player_card_id=_validate_card_id(
            entry.get("player_card"), deck_id_set, index, "player_card"
        ),
        player_wildcard=_validate_wildcard(
            entry.get("player_wildcard"), index, "player_wildcard"
        ),
        npc_card_id=_validate_card_id(
            entry.get("npc_card"), deck_id_set, index, "npc_card"
        ),
        npc_wildcard=_validate_wildcard(
            entry.get("npc_wildcard"), index, "npc_wildcard"
        ),
    )


def _validate_card_id(
    value, deck_id_set: set[str], index: int, field_name: str
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"rounds[{index}].{field_name} must be a string")
    if value not in deck_id_set:
        raise ValueError(
            f"rounds[{index}].{field_name} references unknown card id: {value}"
        )
    return value


def _validate_wildcard(value, index: int, field_name: str) -> Janken | None:
    if value is None:
        return None
    if not isinstance(value, str) or value not in _VALID_WILDCARD_VALUES:
        raise ValueError(
            f"rounds[{index}].{field_name} must be one of "
            f"{sorted(_VALID_WILDCARD_VALUES)}"
        )
    return Janken(value)
