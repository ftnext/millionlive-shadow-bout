from dataclasses import replace

from shadow_bout.effect_handlers.common import (
    _immune_blocked_state,
    _opponent_is_immune,
)
from shadow_bout.effect_handlers.registry import register
from shadow_bout.effect_utils import (
    get_opponent_side,
    get_player_state,
)
from shadow_bout.models import (
    Card,
    GameState,
    PendingEffectContext,
    Phase,
    Side,
)


@register("special")
def effect_special(state: GameState, side: Side, card: Card) -> GameState:
    if _opponent_is_immune(state, side):
        return _immune_blocked_state(state, card)

    ctx = PendingEffectContext(side=side, card_id=card.id, effect="special")
    state = replace(
        state, phase=Phase.INTERACTIVE_EFFECT, effect_step=0, pending_effect_context=ctx
    )
    return replace(
        state,
        battle_log=state.battle_log + [f"{card.name}の効果発動: 宣言待機中..."],
    )


@register("choose")
def effect_choose(state: GameState, side: Side, card: Card) -> GameState:
    choose_variant = {
        "card_26": "yuriko_choose",
        "c26": "yuriko_choose",
        "card_45": "karen_choose",
        "c45": "karen_choose",
    }.get(card.id, "generic_choose")
    ctx = PendingEffectContext(
        side=side,
        card_id=card.id,
        effect="choose",
        payload={"choose_variant": choose_variant},
    )
    state = replace(
        state, phase=Phase.INTERACTIVE_EFFECT, effect_step=0, pending_effect_context=ctx
    )
    return replace(
        state, battle_log=state.battle_log + [f"{card.name}の効果発動: 選択待機中..."]
    )


@register("choose_multiple")
def effect_choose_multiple(state: GameState, side: Side, card: Card) -> GameState:
    p_state = get_player_state(state, side)
    if not p_state.hand and not p_state.deck:
        return replace(
            state,
            battle_log=state.battle_log
            + [f"{card.name}の効果発動: 発動可能な効果がないため不発"],
        )

    ctx = PendingEffectContext(side=side, card_id=card.id, effect="choose_multiple")
    state = replace(
        state, phase=Phase.INTERACTIVE_EFFECT, effect_step=0, pending_effect_context=ctx
    )
    return replace(
        state,
        battle_log=state.battle_log + [f"{card.name}の効果発動: 複数選択待機中..."],
    )


@register("search_and_swap")
def effect_search_and_swap(state: GameState, side: Side, card: Card) -> GameState:
    ctx = PendingEffectContext(side=side, card_id=card.id, effect="search_and_swap")
    state = replace(
        state, phase=Phase.INTERACTIVE_EFFECT, effect_step=0, pending_effect_context=ctx
    )
    return replace(
        state,
        battle_log=state.battle_log + [f"{card.name}の効果発動: 交換選択待機中..."],
    )


@register("swap")
def effect_swap(state: GameState, side: Side, card: Card) -> GameState:
    ctx = PendingEffectContext(side=side, card_id=card.id, effect="swap")
    state = replace(
        state, phase=Phase.INTERACTIVE_EFFECT, effect_step=0, pending_effect_context=ctx
    )
    return replace(
        state,
        battle_log=state.battle_log + [f"{card.name}の効果発動: 入れ替え選択待機中..."],
    )


@register("tutor_play")
def effect_tutor_play(state: GameState, side: Side, card: Card) -> GameState:
    ctx = PendingEffectContext(side=side, card_id=card.id, effect="tutor_play")
    state = replace(
        state, phase=Phase.INTERACTIVE_EFFECT, effect_step=0, pending_effect_context=ctx
    )
    return replace(
        state,
        battle_log=state.battle_log
        + [f"{card.name}の効果発動: 場に出すカード選択待機中..."],
    )


@register("swap_opponent")
def effect_swap_opponent(state: GameState, side: Side, card: Card) -> GameState:
    if _opponent_is_immune(state, side):
        return _immune_blocked_state(state, card)

    ctx = PendingEffectContext(side=side, card_id=card.id, effect="swap_opponent")
    state = replace(
        state, phase=Phase.INTERACTIVE_EFFECT, effect_step=0, pending_effect_context=ctx
    )
    return replace(
        state,
        battle_log=state.battle_log
        + [f"{card.name}の効果発動: 相手手札確認・入れ替え待機中..."],
    )


@register("removal")
def effect_removal(state: GameState, side: Side, card: Card) -> GameState:
    if _opponent_is_immune(state, side):
        return _immune_blocked_state(state, card)

    ctx = PendingEffectContext(side=side, card_id=card.id, effect="removal")
    state = replace(
        state, phase=Phase.INTERACTIVE_EFFECT, effect_step=0, pending_effect_context=ctx
    )
    return replace(
        state, battle_log=state.battle_log + [f"{card.name}の効果発動: 発動待機中..."]
    )


@register("salvage")
def effect_salvage(state: GameState, side: Side, card: Card) -> GameState:
    ctx = PendingEffectContext(side=side, card_id=card.id, effect="salvage")
    state = replace(
        state, phase=Phase.INTERACTIVE_EFFECT, effect_step=0, pending_effect_context=ctx
    )
    return replace(
        state,
        battle_log=state.battle_log + [f"{card.name}の効果発動: 回収選択待機中..."],
    )


@register("reorder")
def effect_reorder(state: GameState, side: Side, card: Card) -> GameState:
    opponent_state = get_player_state(state, get_opponent_side(side))
    if len(opponent_state.deck) <= 1:
        return replace(
            state,
            battle_log=state.battle_log
            + [f"{card.name}の効果発動: 並び替える相手の山札がないため不発"],
        )

    ctx = PendingEffectContext(side=side, card_id=card.id, effect="reorder")
    state = replace(
        state, phase=Phase.INTERACTIVE_EFFECT, effect_step=0, pending_effect_context=ctx
    )
    return replace(
        state,
        battle_log=state.battle_log
        + [f"{card.name}の効果発動: 相手山札の並び替え待機中..."],
    )
