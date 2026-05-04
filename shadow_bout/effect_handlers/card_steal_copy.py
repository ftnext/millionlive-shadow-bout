import random
from dataclasses import replace

from shadow_bout.effect_handlers.common import (
    _immune_blocked_state,
    _opponent_is_immune,
)
from shadow_bout.effect_handlers.registry import get_effect_handler, register
from shadow_bout.effect_utils import (
    get_opponent_side,
    get_player_state,
    update_player,
)
from shadow_bout.models import (
    Card,
    GameState,
    PendingEffectContext,
    Phase,
    Side,
)


@register("steal_draw")
def effect_steal_draw(state: GameState, side: Side, card: Card) -> GameState:
    opp_side = get_opponent_side(side)
    if _opponent_is_immune(state, side):
        return _immune_blocked_state(state, card)

    opp_state = get_player_state(state, opp_side)

    if not opp_state.deck:
        return replace(
            state,
            battle_log=state.battle_log
            + [f"{card.name}の効果発動: 相手の山札が空のため不発"],
        )

    stolen = opp_state.deck[0]
    state = update_player(
        state,
        opp_side,
        deck=opp_state.deck[1:],
    )

    own_state = get_player_state(state, side)
    state = update_player(
        state,
        side,
        hand=own_state.hand + [stolen],
    )

    return replace(
        state,
        battle_log=state.battle_log
        + [
            f"{card.name}の効果発動: 相手の山札の上から{stolen.name}を奪って手札に加えた"
        ],
    )


@register("steal_hand")
def effect_steal_hand(state: GameState, side: Side, card: Card) -> GameState:
    opp_side = get_opponent_side(side)
    if _opponent_is_immune(state, side):
        return _immune_blocked_state(state, card)

    opp_state = get_player_state(state, opp_side)

    if not opp_state.hand:
        return replace(
            state,
            battle_log=state.battle_log
            + [f"{card.name}の効果発動: 相手の手札が空のため不発"],
        )

    stolen_idx = random.randrange(len(opp_state.hand))
    stolen = opp_state.hand[stolen_idx]
    state = update_player(
        state,
        opp_side,
        hand=[c for i, c in enumerate(opp_state.hand) if i != stolen_idx],
    )

    own_state = get_player_state(state, side)
    state = update_player(
        state,
        side,
        hand=own_state.hand + [stolen],
    )

    return replace(
        state,
        battle_log=state.battle_log
        + [f"{card.name}の効果発動: 相手の手札から{stolen.name}を奪って手札に加えた"],
    )


@register("copy_hand")
def effect_copy_hand(state: GameState, side: Side, card: Card) -> GameState:
    p_state = get_player_state(state, side)
    if not p_state.hand:
        return state

    ctx = PendingEffectContext(side=side, card_id=card.id, effect="copy_hand")
    state = replace(
        state, phase=Phase.INTERACTIVE_EFFECT, effect_step=0, pending_effect_context=ctx
    )
    return replace(
        state,
        battle_log=state.battle_log + [f"{card.name}の効果発動: 対象選択待機中..."],
    )


@register("copy_effect")
def effect_copy_effect(state: GameState, side: Side, card: Card) -> GameState:
    p_state = get_player_state(state, side)
    if not p_state.deck:
        return state

    top_card = p_state.deck[0]
    new_deck = p_state.deck[1:] + [top_card]
    state = update_player(state, side, deck=new_deck)

    state = replace(
        state,
        battle_log=state.battle_log
        + [f"{card.name}の効果発動: 山札の一番上({top_card.name})の効果を発動"],
    )

    if top_card.effect and top_card.effect.type.value == "copy_effect":
        return replace(
            state, battle_log=state.battle_log + ["-> copy_effectのため不発"]
        )
    if top_card.effect and get_effect_handler(top_card.effect.type.value):
        new_queue = [(side, top_card)] + state.effect_queue
        return replace(state, effect_queue=new_queue)

    return state
