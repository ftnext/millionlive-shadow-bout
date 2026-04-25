import json
from pathlib import Path

from shadow_bout.models import Card, Janken


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
            all_cards.append(
                Card(
                    id=data["id"],
                    name=data["name"],
                    janken=Janken(data["janken"]),
                    base_point=data["basePoint"],
                )
            )

    if card_ids:
        id_to_card = {card.id: card for card in all_cards}
        return [id_to_card[cid] for cid in card_ids if cid in id_to_card]

    return all_cards
