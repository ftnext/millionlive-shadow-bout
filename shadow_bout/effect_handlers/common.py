from dataclasses import replace

from shadow_bout.effect_utils import (
    get_opponent_side,
    get_player_state,
    is_immune_to_opponent_effect,
)
from shadow_bout.models import Card, GameState, Janken, Phase, Side

JANKEN_NAMES = {
    Janken.ROCK: "グー",
    Janken.SCISSORS: "チョキ",
    Janken.PAPER: "パー",
    Janken.WILDCARD: "ワイルド",
}


def _finish_interactive_effect(state: GameState, log_msg: str) -> GameState:
    return replace(
        state,
        phase=Phase.EFFECT_RESOLUTION,
        pending_effect_context=None,
        battle_log=state.battle_log + [log_msg],
    )


def _find_card(cards: list[Card], card_id: str | None) -> Card | None:
    if card_id is None:
        return None
    return next((card for card in cards if card.id == card_id), None)


def _find_card_by_id(state: GameState, side: Side, card_id: str | None) -> Card | None:
    p_state = get_player_state(state, side)
    card_lists = [
        p_state.hand,
        p_state.deck,
        p_state.discard,
        p_state.won_cards,
        p_state.draw_stock,
    ]
    if state.current_battle is not None:
        card_lists.append(
            [
                state.current_battle.player_card,
                state.current_battle.npc_card,
            ]
        )
    return next(
        (card for cards in card_lists for card in cards if card.id == card_id), None
    )


def _remove_first_card_by_id(cards: list[Card], card_id: str) -> list[Card]:
    removed = False
    remaining: list[Card] = []
    for card in cards:
        if not removed and card.id == card_id:
            removed = True
            continue
        remaining.append(card)
    return remaining


def _parse_card_ids(choice: str | None) -> list[str]:
    if not choice:
        return []
    return [card_id for card_id in choice.split(",") if card_id]


def _immune_blocked_state(state: GameState, card: Card) -> GameState:
    return replace(
        state,
        battle_log=state.battle_log
        + [f"{card.name}の効果発動: 相手は戦具効果を受けないため不発"],
    )


def _opponent_is_immune(state: GameState, side: Side) -> bool:
    return is_immune_to_opponent_effect(state, side, get_opponent_side(side))
