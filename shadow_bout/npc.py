import random
from typing import Protocol

from shadow_bout.models import Card, GameState
from shadow_bout.scenario import Scenario, ScenarioRound


class NpcStrategy(Protocol):
    def select_card(self, hand: list[Card], game_state: GameState) -> Card: ...
    def choose_effect(self, choices: list[str], game_state: GameState) -> str: ...
    def select_target(self, candidates: list[Card], game_state: GameState) -> Card: ...
    def should_activate(self, card: Card, game_state: GameState) -> bool: ...
    def declare_wildcard_janken(
        self, choices: list[str], game_state: GameState
    ) -> str: ...


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

    def declare_wildcard_janken(self, choices: list[str], game_state: GameState) -> str:
        return random.choice(choices)


class ScriptedStrategy:
    """シナリオ指定があればその通りに、無ければ Random フォールバック。"""

    def __init__(self, scenario: Scenario):
        self._rounds: list[ScenarioRound | None] = list(scenario.rounds)
        self._fallback = RandomStrategy()

    def _round_spec(self, game_state: GameState) -> ScenarioRound | None:
        idx = game_state.round_number - 1
        if 0 <= idx < len(self._rounds):
            return self._rounds[idx]
        return None

    def select_card(self, hand: list[Card], game_state: GameState) -> Card:
        spec = self._round_spec(game_state)
        if spec and spec.npc_card_id:
            match = next((c for c in hand if c.id == spec.npc_card_id), None)
            if match is None:
                raise ValueError(
                    f"scripted npc_card '{spec.npc_card_id}' not in NPC hand at "
                    f"round {game_state.round_number}; check the scenario's "
                    f"hand setup or earlier rounds"
                )
            return match
        return self._fallback.select_card(hand, game_state)

    def declare_wildcard_janken(self, choices: list[str], game_state: GameState) -> str:
        spec = self._round_spec(game_state)
        if spec and spec.npc_wildcard is not None:
            return spec.npc_wildcard.value
        return self._fallback.declare_wildcard_janken(choices, game_state)

    def choose_effect(self, choices: list[str], game_state: GameState) -> str:
        return self._fallback.choose_effect(choices, game_state)

    def select_target(self, candidates: list[Card], game_state: GameState) -> Card:
        return self._fallback.select_target(candidates, game_state)

    def should_activate(self, card: Card, game_state: GameState) -> bool:
        return self._fallback.should_activate(card, game_state)
