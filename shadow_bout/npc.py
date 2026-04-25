import random
from typing import Protocol

from shadow_bout.models import Card, GameState


class NpcStrategy(Protocol):
    def select_card(self, hand: list[Card], game_state: GameState) -> Card: ...
    def choose_effect(self, choices: list[str], game_state: GameState) -> str: ...
    def select_target(self, candidates: list[Card], game_state: GameState) -> Card: ...
    def should_activate(self, card: Card, game_state: GameState) -> bool: ...


class RandomStrategy:
    """v0.2: ランダムに選択を行う"""

    def select_card(self, hand: list[Card], game_state: GameState) -> Card:
        return random.choice(hand)

    def choose_effect(self, choices: list[str], game_state: GameState) -> str:
        return random.choice(choices)

    def select_target(self, candidates: list[Card], game_state: GameState) -> Card:
        return random.choice(candidates)

    def should_activate(self, card: Card, game_state: GameState) -> bool:
        return random.choice([True, False])
