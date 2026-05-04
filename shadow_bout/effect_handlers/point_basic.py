from dataclasses import replace

from shadow_bout.effect_handlers.common import (
    JANKEN_NAMES,
    _immune_blocked_state,
    _opponent_is_immune,
)
from shadow_bout.effect_handlers.registry import register
from shadow_bout.effect_utils import (
    get_opponent_side,
    get_player_state,
    set_battle_janken_override,
    update_player,
)
from shadow_bout.models import (
    Card,
    GameState,
    Janken,
    PendingEffectContext,
    Phase,
    Side,
)


@register("null")
def effect_null(state: GameState, side: Side, card: Card) -> GameState:
    return state


@register("immune")
def effect_immune(state: GameState, side: Side, card: Card) -> GameState:
    return replace(
        state,
        battle_log=state.battle_log
        + [f"{card.name}の効果発動: 相手の戦具効果を受けない"],
    )


@register("buff")
def effect_buff(state: GameState, side: Side, card: Card) -> GameState:
    p_state = get_player_state(state, side)
    new_mod = p_state.point_modifier + int(card.effect.value or 0)
    state = update_player(state, side, point_modifier=new_mod)
    return replace(
        state,
        battle_log=state.battle_log
        + [f"{card.name}の効果発動: ポイント+{card.effect.value}"],
    )


@register("buff_and_peek")
def effect_buff_and_peek(state: GameState, side: Side, card: Card) -> GameState:
    p_state = get_player_state(state, side)
    bonus = int(card.effect.value or 0)
    state = update_player(state, side, point_modifier=p_state.point_modifier + bonus)

    updated_state = get_player_state(state, side)
    if not updated_state.deck:
        return replace(
            state,
            battle_log=state.battle_log
            + [f"{card.name}の効果発動: ポイント+{bonus}、山札が空のため確認できない"],
        )

    top_card = updated_state.deck[0]
    return replace(
        state,
        battle_log=state.battle_log
        + [f"{card.name}の効果発動: ポイント+{bonus}、山札の一番上は{top_card.name}"],
    )


@register("buff_dynamic")
def effect_buff_dynamic(state: GameState, side: Side, card: Card) -> GameState:
    p_state = get_player_state(state, side)
    bonus = len(p_state.hand) * int(card.effect.value or 1)
    new_mod = p_state.point_modifier + bonus
    state = update_player(state, side, point_modifier=new_mod)
    return replace(
        state,
        battle_log=state.battle_log
        + [f"{card.name}の効果発動: 手札枚数x{card.effect.value} = +{bonus}"],
    )


@register("buff_next")
def effect_buff_next(state: GameState, side: Side, card: Card) -> GameState:
    p_state = get_player_state(state, side)
    bonus = int(card.effect.value or 0)
    state = update_player(
        state,
        side,
        next_round_point_modifier=p_state.next_round_point_modifier + bonus,
    )
    return replace(
        state,
        battle_log=state.battle_log
        + [f"{card.name}の効果発動: 次ラウンドのポイント{bonus:+d}"],
    )


@register("buff_snowball")
def effect_buff_snowball(state: GameState, side: Side, card: Card) -> GameState:
    p_state = get_player_state(state, side)
    bonus = int(card.effect.value or 0)
    state = update_player(
        state,
        side,
        point_modifier=p_state.point_modifier + bonus,
    )
    return replace(
        state,
        pending_next_round_buff_on_win=(
            state.pending_next_round_buff_on_win + ((side, bonus),)
        ),
        battle_log=state.battle_log
        + [
            f"{card.name}の効果発動: この勝負のポイント{bonus:+d}、"
            f"勝利時に次ラウンドのポイント{bonus:+d}"
        ],
    )


@register("change_janken")
def effect_change_janken(state: GameState, side: Side, card: Card) -> GameState:
    opp_side = get_opponent_side(side)
    if _opponent_is_immune(state, side):
        return _immune_blocked_state(state, card)

    target_janken = Janken(card.effect.value)
    target_name = JANKEN_NAMES[target_janken]

    # card_09（律子）は「次の勝負」の相手の場/手札に適用する。
    if card.id in ("card_09", "c9"):
        state = update_player(
            state,
            opp_side,
            next_round_janken_override=target_janken,
        )
        return replace(
            state,
            battle_log=state.battle_log
            + [f"{card.name}の効果発動: 次ラウンドの相手の場と手札を{target_name}扱い"],
        )

    # card_28（亜利沙）は即時に現在の相手場カードだけへ適用し、効果後の再判定に反映する。
    if card.id in ("card_28", "c28"):
        state = set_battle_janken_override(state, opp_side, target_janken)
        return replace(
            state,
            battle_log=state.battle_log
            + [f"{card.name}の効果発動: 相手の場のカードを{target_name}扱い"],
        )

    return replace(
        state,
        battle_log=state.battle_log + [f"{card.name}の効果発動: 未対応カードID"],
    )


@register("buff_scaling")
def effect_buff_scaling(state: GameState, side: Side, card: Card) -> GameState:
    p_state = get_player_state(state, side)
    bonus = state.round_number * 2
    state = update_player(state, side, point_modifier=p_state.point_modifier + bonus)
    return replace(
        state,
        battle_log=state.battle_log
        + [f"{card.name}の効果発動: R{state.round_number}のためポイント+{bonus}"],
    )


@register("debuff")
def effect_debuff(state: GameState, side: Side, card: Card) -> GameState:
    opp_side = get_opponent_side(side)
    if _opponent_is_immune(state, side):
        return _immune_blocked_state(state, card)

    opp_state = get_player_state(state, opp_side)

    if card.id in ("card_04", "c4"):
        current_battle = state.current_battle
        opp_card = (
            current_battle.npc_card
            if opp_side == Side.NPC
            else current_battle.player_card
        )
        conditional = (
            opp_state.conditional_point_modifier_non_wildcard
            if opp_card.janken != Janken.WILDCARD
            else 0
        )
        current_point = opp_card.base_point + opp_state.point_modifier + conditional
        halved_point = current_point // 2
        new_modifier = halved_point - opp_card.base_point - conditional
        state = update_player(state, opp_side, point_modifier=new_modifier)
        return replace(
            state,
            battle_log=state.battle_log
            + [f"{card.name}の効果発動: 相手のポイントを半分(切り捨て)にした"],
        )

    if card.id in ("card_17", "c17"):
        debuff = len(opp_state.hand) * int(card.effect.value or 0)
        state = update_player(
            state, opp_side, point_modifier=opp_state.point_modifier + debuff
        )
        return replace(
            state,
            battle_log=state.battle_log
            + [f"{card.name}の効果発動: 相手の手札枚数ぶんポイント{debuff:+d}"],
        )

    return state


@register("debuff_counterable")
def effect_debuff_counterable(state: GameState, side: Side, card: Card) -> GameState:
    opp_side = get_opponent_side(side)
    if _opponent_is_immune(state, side):
        return _immune_blocked_state(state, card)

    debuff = int(card.effect.value or 0)
    opp_state = get_player_state(state, opp_side)
    if not opp_state.hand:
        state = update_player(
            state,
            opp_side,
            point_modifier=opp_state.point_modifier + debuff,
        )
        return replace(
            state,
            battle_log=state.battle_log
            + [f"{card.name}の効果発動: 相手の手札がないため相手のポイント{debuff:+d}"],
        )

    ctx = PendingEffectContext(
        side=opp_side,
        card_id=card.id,
        effect="debuff_counterable",
        payload={"debuff": debuff},
    )
    state = replace(
        state, phase=Phase.INTERACTIVE_EFFECT, effect_step=0, pending_effect_context=ctx
    )
    return replace(
        state,
        battle_log=state.battle_log
        + [f"{card.name}の効果発動: 相手の無効化選択待機中..."],
    )


@register("set_point")
def effect_set_point(state: GameState, side: Side, card: Card) -> GameState:
    opp_side = get_opponent_side(side)
    if _opponent_is_immune(state, side):
        return _immune_blocked_state(state, card)

    opp_state = get_player_state(state, opp_side)

    set_value = int(card.effect.value or 0)
    current_battle = state.current_battle
    opp_card = (
        current_battle.npc_card if opp_side == Side.NPC else current_battle.player_card
    )
    conditional = (
        opp_state.conditional_point_modifier_non_wildcard
        if opp_card.janken != Janken.WILDCARD
        else 0
    )
    new_modifier = set_value - opp_card.base_point - conditional
    state = update_player(state, opp_side, point_modifier=new_modifier)
    return replace(
        state,
        battle_log=state.battle_log
        + [f"{card.name}の効果発動: 相手のポイントを{set_value}にした"],
    )


@register("set_point_match")
def effect_set_point_match(state: GameState, side: Side, card: Card) -> GameState:
    ctx = PendingEffectContext(side=side, card_id=card.id, effect="set_point_match")
    state = replace(
        state, phase=Phase.INTERACTIVE_EFFECT, effect_step=0, pending_effect_context=ctx
    )
    return replace(
        state,
        battle_log=state.battle_log + [f"{card.name}の効果発動: 発動選択待機中..."],
    )


@register("negate")
def effect_negate(state: GameState, side: Side, card: Card) -> GameState:
    opp_side = get_opponent_side(side)
    if _opponent_is_immune(state, side):
        return _immune_blocked_state(state, card)

    state = update_player(state, opp_side, effect_negated=True)
    return replace(
        state,
        battle_log=state.battle_log
        + [f"{card.name}の効果発動: 相手の戦具効果を無効化"],
    )
