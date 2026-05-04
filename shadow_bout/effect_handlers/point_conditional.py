from dataclasses import replace

from shadow_bout.effect_handlers.common import (
    _immune_blocked_state,
    _opponent_is_immune,
)
from shadow_bout.effect_handlers.registry import register
from shadow_bout.effect_utils import (
    get_opponent_side,
    get_player_state,
    update_player,
)
from shadow_bout.models import (
    Card,
    GameState,
    Janken,
    PersistentPointEffect,
    Side,
)


@register("conditional_buff")
def effect_conditional_buff(state: GameState, side: Side, card: Card) -> GameState:
    p_state = get_player_state(state, side)
    opp_side = get_opponent_side(side)
    opp_state = get_player_state(state, opp_side)

    own_won_total = sum(won.base_point for won in p_state.won_cards)
    opp_won_total = sum(won.base_point for won in opp_state.won_cards)
    bonus = int(card.effect.value or 0)

    if opp_won_total > own_won_total:
        state = update_player(
            state,
            side,
            point_modifier=p_state.point_modifier + bonus,
        )
        return replace(
            state,
            battle_log=state.battle_log
            + [
                f"{card.name}の効果発動: 相手の勝ち札合計({opp_won_total}) > 自分({own_won_total})のためポイント+{bonus}"
            ],
        )

    return replace(
        state,
        battle_log=state.battle_log
        + [
            f"{card.name}の効果発動: 相手の勝ち札合計({opp_won_total}) <= 自分({own_won_total})のため不発"
        ],
    )


@register("conditional_negate_buff")
def effect_conditional_negate_buff(
    state: GameState, side: Side, card: Card
) -> GameState:
    opp_side = get_opponent_side(side)
    opponent_is_immune = _opponent_is_immune(state, side)

    current_battle = state.current_battle
    if current_battle is None:
        return replace(
            state,
            battle_log=state.battle_log
            + [f"{card.name}の効果発動: 場のカードがないため不発"],
        )

    p_state = get_player_state(state, side)
    opp_state = get_player_state(state, opp_side)
    opp_card = (
        current_battle.npc_card if opp_side == Side.NPC else current_battle.player_card
    )
    conditional = (
        opp_state.conditional_point_modifier_non_wildcard
        if opp_card.janken != Janken.WILDCARD
        else 0
    )
    opponent_point = opp_card.base_point + opp_state.point_modifier + conditional

    if opponent_point % 2 == 0:
        return replace(
            state,
            battle_log=state.battle_log
            + [
                f"{card.name}の効果発動: 相手のポイント({opponent_point})が偶数のため不発"
            ],
        )

    bonus = int(card.effect.value or 0)
    if not opponent_is_immune:
        state = update_player(state, opp_side, effect_negated=True)
    state = update_player(state, side, point_modifier=p_state.point_modifier + bonus)
    if opponent_is_immune:
        return replace(
            state,
            battle_log=state.battle_log
            + [
                f"{card.name}の効果発動: 相手のポイント({opponent_point})が奇数だが、相手は戦具効果を受けないため無効化できず、ポイント+{bonus}"
            ],
        )

    return replace(
        state,
        battle_log=state.battle_log
        + [
            f"{card.name}の効果発動: 相手のポイント({opponent_point})が奇数のため相手の戦具効果を無効化し、ポイント+{bonus}"
        ],
    )


@register("conditional_debuff_next")
def effect_conditional_debuff_next(
    state: GameState, side: Side, card: Card
) -> GameState:
    opp_side = get_opponent_side(side)
    if _opponent_is_immune(state, side):
        return _immune_blocked_state(state, card)

    opp_state = get_player_state(state, opp_side)
    debuff = int(card.effect.value or 0)
    state = update_player(
        state,
        opp_side,
        next_round_conditional_point_modifier_non_wildcard=(
            opp_state.next_round_conditional_point_modifier_non_wildcard + debuff
        ),
    )
    return replace(
        state,
        battle_log=state.battle_log
        + [f"{card.name}の効果発動: 相手の次ラウンド(バー以外)のポイント{debuff:+d}"],
    )


@register("conditional_debuff_draw")
def effect_conditional_debuff_draw(
    state: GameState, side: Side, card: Card
) -> GameState:
    opp_side = get_opponent_side(side)
    current_battle = state.current_battle
    if current_battle is None:
        return replace(
            state,
            battle_log=state.battle_log
            + [f"{card.name}の効果発動: 場のカードがないため不発"],
        )

    opp_state = get_player_state(state, opp_side)
    opp_card = (
        current_battle.npc_card if opp_side == Side.NPC else current_battle.player_card
    )
    conditional = (
        opp_state.conditional_point_modifier_non_wildcard
        if opp_card.janken != Janken.WILDCARD
        else 0
    )
    opponent_point = opp_card.base_point + opp_state.point_modifier + conditional
    debuff = int(card.effect.value or 0)
    draw_count = 1
    logs = [f"勝利時に{draw_count}枚ドローを予約"]

    if opponent_point <= 15:
        if _opponent_is_immune(state, side):
            logs.append(
                f"相手のポイント({opponent_point})は15以下だが、"
                "相手は戦具効果を受けないためポイント減少は不発"
            )
        else:
            state = update_player(
                state,
                opp_side,
                point_modifier=opp_state.point_modifier + debuff,
            )
            logs.append(
                f"相手のポイント({opponent_point})が15以下のため相手{debuff:+d}"
            )
    else:
        logs.append(f"相手のポイント({opponent_point})が16以上のためポイント減少は不発")

    return replace(
        state,
        pending_draw_on_win=state.pending_draw_on_win + ((side, draw_count),),
        battle_log=state.battle_log + [f"{card.name}の効果発動: {'、'.join(logs)}"],
    )


@register("debuff_persistent")
def effect_debuff_persistent(state: GameState, side: Side, card: Card) -> GameState:
    opp_side = get_opponent_side(side)
    if _opponent_is_immune(state, side):
        return _immune_blocked_state(state, card)

    opp_state = get_player_state(state, opp_side)
    debuff = int(card.effect.value or 0)
    state = update_player(
        state, opp_side, point_modifier=opp_state.point_modifier + debuff
    )
    # 「このターンと次のターン」: 現ターンは即時適用し、次ターン分を継続効果として保持
    updated_opp_state = get_player_state(state, opp_side)
    state = update_player(
        state,
        opp_side,
        persistent_point_effects=updated_opp_state.persistent_point_effects
        + (PersistentPointEffect(value=debuff, remaining_turns=1),),
    )
    return replace(
        state,
        battle_log=state.battle_log
        + [f"{card.name}の効果発動: 相手のポイントをこのターンと次ターン{debuff:+d}"],
    )


@register("debuff_conditional")
def effect_debuff_conditional(state: GameState, side: Side, card: Card) -> GameState:
    opp_side = get_opponent_side(side)
    if _opponent_is_immune(state, side):
        return _immune_blocked_state(state, card)

    opp_state = get_player_state(state, opp_side)
    debuff = int(card.effect.value or 0)

    if card.id == "card_18":
        return replace(
            state,
            battle_log=state.battle_log
            + [
                f"{card.name}の効果発動: この勝負で敗北した場合に次ラウンド(バー以外)ポイント{debuff:+d}"
            ],
            pending_conditional_debuff_on_loss=(
                state.pending_conditional_debuff_on_loss + ((side, debuff),)
            ),
        )

    if card.id == "card_30":
        if state.round_number >= 3:
            state = update_player(
                state,
                opp_side,
                next_round_conditional_point_modifier_non_wildcard=(
                    opp_state.next_round_conditional_point_modifier_non_wildcard
                    + debuff
                ),
            )
            return replace(
                state,
                battle_log=state.battle_log
                + [
                    f"{card.name}の効果発動: 3戦目以降のため相手の次ラウンド(バー以外)ポイント{debuff:+d}"
                ],
            )

        return replace(
            state,
            battle_log=state.battle_log
            + [f"{card.name}の効果発動: 3戦目未満のため不発(R{state.round_number})"],
        )

    return replace(
        state,
        battle_log=state.battle_log
        + [f"{card.name}の効果発動: 未対応の条件カードID({card.id})"],
    )
