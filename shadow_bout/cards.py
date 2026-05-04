import json
import random
from pathlib import Path

from shadow_bout.models import Card, Effect, EffectType, Janken


def load_deck(
    card_ids: list[str] | None = None, jsonl_path: Path = Path("cards.jsonl")
) -> list[Card]:
    """cards.jsonl から全カードを読み込み、指定IDがある場合は13枚に絞って返す"""
    all_cards = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            data = json.loads(line)
            effect_data = data.get("effect")
            effect = None
            if effect_data:
                try:
                    effect = Effect(
                        type=EffectType(effect_data["type"]),
                        description=effect_data["description"],
                        value=effect_data.get("value"),
                    )
                except ValueError:
                    pass

            all_cards.append(
                Card(
                    id=data["id"],
                    name=data["name"],
                    kana=data["kana"],
                    janken=Janken(data["janken"]),
                    base_point=data["basePoint"],
                    effect=effect,
                )
            )

    if card_ids:
        id_to_card = {card.id: card for card in all_cards}
        return [id_to_card[cid] for cid in card_ids if cid in id_to_card]

    return all_cards


def select_random_deck(
    size: int = 13, jsonl_path: Path = Path("cards.jsonl")
) -> list[Card]:
    """cards.jsonl の全カードから重複なく size 枚をランダム抽選して返す。"""
    all_cards = load_deck(jsonl_path=jsonl_path)
    return random.sample(all_cards, size)
