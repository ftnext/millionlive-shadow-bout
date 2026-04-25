import random
from typing import Protocol

from shadow_bout.models import Card, GameState


class NpcStrategy(Protocol):
    def select_card(self, hand: list[Card], game_state: GameState) -> Card: ...


class RandomStrategy:
    """v0.1: 手札からランダムに1枚選択"""

    def select_card(self, hand: list[Card], game_state: GameState) -> Card:
        return random.choice(hand)
