from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

REGISTER_PATTERN = re.compile(r'@register\("([^"]+)"\)')


def extract_registered_types(effect_handlers_path: Path) -> set[str]:
    content = effect_handlers_path.read_text(encoding="utf-8")
    return set(REGISTER_PATTERN.findall(content))


def load_cards(cards_path: Path) -> list[dict]:
    cards: list[dict] = []
    with cards_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            cards.append(json.loads(line))
    return cards


def find_unimplemented_cards(
    cards: list[dict], implemented_types: set[str]
) -> list[dict]:
    unimplemented: list[dict] = []
    for card in cards:
        effect = card.get("effect")
        if not effect:
            continue
        effect_type = effect.get("type")
        if effect_type is None:
            continue
        if effect_type not in implemented_types:
            unimplemented.append(
                {
                    "id": card["id"],
                    "name": card["name"],
                    "type": effect_type,
                }
            )
    return unimplemented


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cards_path = repo_root / "cards.jsonl"
    effect_handlers_path = repo_root / "shadow_bout" / "effect_handlers.py"

    implemented_types = extract_registered_types(effect_handlers_path)
    cards = load_cards(cards_path)
    unimplemented = find_unimplemented_cards(cards, implemented_types)

    print("未実装カード一覧（id/name/type）")
    for card in unimplemented:
        print(f"- {card['id']} / {card['name']} / {card['type']}")

    print("\n未実装typeの件数集計")
    type_counter = Counter(card["type"] for card in unimplemented)
    for effect_type, count in sorted(type_counter.items()):
        print(f"- {effect_type}: {count}")


if __name__ == "__main__":
    main()
