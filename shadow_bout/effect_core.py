from dataclasses import replace

from shadow_bout.effect_handlers import get_effect_handler, resume_pending_effect
from shadow_bout.effect_scoring import (
    resolve_post_effect_points,
    resolve_post_effect_skipped,
)
from shadow_bout.effect_utils import get_player_state
from shadow_bout.models import Card, GameState, Phase, Side

_OPPONENT_TARGETING_EFFECTS = frozenset(
    {
        "ban",
        "conditional_debuff_next",
        "curse",
        "debuff",
        "debuff_conditional",
        "debuff_persistent",
        "force_play",
        "negate",
        "reveal",
        "reveal_all",
        "set_point",
        "steal_draw",
        "steal_hand",
    }
)


def _is_immune_active(state: GameState, side: Side) -> bool:
    battle = state.current_battle
    if battle is None:
        return False
    card = battle.player_card if side == Side.PLAYER else battle.npc_card
    return bool(card.effect and card.effect.type.value == "immune")


def _is_blocked_by_immune(state: GameState, side: Side, card: Card) -> bool:
    if not card.effect or card.effect.type.value not in _OPPONENT_TARGETING_EFFECTS:
        return False
    opp_side = Side.NPC if side == Side.PLAYER else Side.PLAYER
    return _is_immune_active(state, opp_side)


def init_effect_resolution(state: GameState, p_card: Card, n_card: Card) -> GameState:
    # Sort order: smaller base_point first, then kana.
    cards = [(Side.PLAYER, p_card), (Side.NPC, n_card)]
    cards.sort(key=lambda x: (x[1].base_point, x[1].kana))

    return replace(state, effect_queue=cards, phase=Phase.EFFECT_RESOLUTION)


def process_next_effect(state: GameState) -> GameState:
    if state.phase == Phase.INTERACTIVE_EFFECT:
        return state

    current_state = state
    while current_state.effect_queue and current_state.phase == Phase.EFFECT_RESOLUTION:
        if current_state.removal_activated:
            current_state = replace(current_state, effect_queue=[])
            break

        side, card = current_state.effect_queue[0]

        p_state = get_player_state(current_state, side)
        if p_state.effect_negated:
            current_state = replace(
                current_state, effect_queue=current_state.effect_queue[1:]
            )
            continue

        if not card.effect:
            current_state = replace(
                current_state, effect_queue=current_state.effect_queue[1:]
            )
            continue

        if _is_blocked_by_immune(current_state, side, card):
            current_state = replace(
                current_state,
                effect_queue=current_state.effect_queue[1:],
                battle_log=current_state.battle_log
                + [f"{card.name}の効果発動: 相手のimmuneにより無効"],
            )
            continue

        handler = get_effect_handler(card.effect.type.value)
        if handler is None:
            current_state = replace(
                current_state, effect_queue=current_state.effect_queue[1:]
            )
            continue

        current_state = replace(
            current_state, effect_queue=current_state.effect_queue[1:]
        )
        current_state = handler(current_state, side, card)

        if current_state.phase == Phase.INTERACTIVE_EFFECT:
            break

    if (
        not current_state.effect_queue
        and current_state.phase == Phase.EFFECT_RESOLUTION
    ):
        if current_state.removal_activated:
            current_state = resolve_post_effect_skipped(current_state)
        else:
            current_state = resolve_post_effect_points(current_state)

    return current_state


def process_next_effect_step(state: GameState) -> GameState:
    if state.phase == Phase.INTERACTIVE_EFFECT:
        return state

    current_state = state
    if current_state.phase != Phase.EFFECT_RESOLUTION:
        return current_state

    while current_state.effect_queue:
        if current_state.removal_activated:
            return replace(current_state, effect_queue=[])

        side, card = current_state.effect_queue[0]
        current_state = replace(
            current_state, effect_queue=current_state.effect_queue[1:]
        )

        p_state = get_player_state(current_state, side)
        if p_state.effect_negated or not card.effect:
            break

        if _is_blocked_by_immune(current_state, side, card):
            current_state = replace(
                current_state,
                battle_log=current_state.battle_log
                + [f"{card.name}の効果発動: 相手のimmuneにより無効"],
            )
            break

        handler = get_effect_handler(card.effect.type.value)
        if handler is None:
            break

        current_state = handler(current_state, side, card)
        break

    if (
        not current_state.effect_queue
        and current_state.phase == Phase.EFFECT_RESOLUTION
    ):
        if current_state.removal_activated:
            return resolve_post_effect_skipped(current_state)
        return resolve_post_effect_points(current_state)

    return current_state


def resume_effect(state: GameState, choice: str | None = None) -> GameState:
    if not state.pending_effect_context:
        return process_next_effect(state)

    state = resume_pending_effect(state, choice)
    return process_next_effect(state)


def resume_effect_step(state: GameState, choice: str | None = None) -> GameState:
    if not state.pending_effect_context:
        return process_next_effect_step(state)

    state = resume_pending_effect(state, choice)
    if state.phase == Phase.EFFECT_RESOLUTION and not state.effect_queue:
        return process_next_effect_step(state)

    return state
