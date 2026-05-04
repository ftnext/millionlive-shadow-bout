from dataclasses import replace

from shadow_bout.effect_utils import get_battle_janken_override, get_effective_janken
from shadow_bout.janken import judge_janken_values
from shadow_bout.models import (
    Card,
    GameState,
    Janken,
    JankenResult,
    Phase,
    PlayerState,
    RoundOutcome,
    Side,
)


def calculate_effective_point(card: Card, player_state: PlayerState) -> int:
    conditional = (
        player_state.conditional_point_modifier_non_wildcard
        if card.janken != Janken.WILDCARD
        else 0
    )
    return card.base_point + player_state.point_modifier + conditional


def _calculate_effective_point_for_side(
    state: GameState, side: Side, card: Card, player_state: PlayerState
) -> int:
    conditional = (
        player_state.conditional_point_modifier_non_wildcard
        if get_effective_janken(state, side, card) != Janken.WILDCARD
        else 0
    )
    return card.base_point + player_state.point_modifier + conditional


def resolve_post_effect_skipped(state: GameState) -> GameState:
    # Julia's removal effect already moved the cards, so the round is consumed
    # without applying the normal win/loss card movement.
    res = state.current_battle
    new_res = replace(res, outcome=RoundOutcome.EVEN, winning_side=None)
    return replace(state, phase=Phase.REVEAL, current_battle=new_res)


def resolve_post_effect_points(state: GameState) -> GameState:
    res = state.current_battle
    p_janken = get_effective_janken(state, Side.PLAYER, res.player_card)
    n_janken = get_effective_janken(state, Side.NPC, res.npc_card)
    battle_janken_changed = (
        get_battle_janken_override(state, Side.PLAYER, res.player_card) is not None
        or get_battle_janken_override(state, Side.NPC, res.npc_card) is not None
    )
    janken_result = (
        judge_janken_values(p_janken, n_janken)
        if battle_janken_changed
        else JankenResult.DRAW
    )
    p_point = None
    n_point = None

    if janken_result == JankenResult.WIN:
        outcome = RoundOutcome.WIN
        winning_side = Side.PLAYER
    elif janken_result == JankenResult.LOSE:
        outcome = RoundOutcome.LOSE
        winning_side = Side.NPC
    else:
        p_point = _calculate_effective_point_for_side(
            state, Side.PLAYER, res.player_card, state.player
        )
        n_point = _calculate_effective_point_for_side(
            state, Side.NPC, res.npc_card, state.npc
        )

        points = {Side.PLAYER: p_point, Side.NPC: n_point}
        for effect in state.point_match_effects:
            points[effect.target_side] = points[effect.source_side]
        p_point = points[Side.PLAYER]
        n_point = points[Side.NPC]

        if p_point > n_point:
            outcome = RoundOutcome.WIN
            winning_side = Side.PLAYER
        elif p_point < n_point:
            outcome = RoundOutcome.LOSE
            winning_side = Side.NPC
        else:
            outcome = RoundOutcome.EVEN
            winning_side = None

    new_res = replace(
        res,
        outcome=outcome,
        winning_side=winning_side,
        janken_result=janken_result,
        player_point=p_point,
        npc_point=n_point,
    )

    if janken_result == JankenResult.DRAW:
        log_msg = f"効果解決後ポイント比較: あなた({p_point}) vs NPC({n_point}) -> "
        if outcome == RoundOutcome.WIN:
            log_msg += "あなたの勝ち！"
        elif outcome == RoundOutcome.LOSE:
            log_msg += "NPCの勝ち！"
        else:
            log_msg += "引き分け！"
    else:
        log_msg = (
            "効果解決後じゃんけん再判定: "
            f"あなた({p_janken.value}) vs NPC({n_janken.value}) -> "
        )
        if outcome == RoundOutcome.WIN:
            log_msg += "あなたの勝ち！"
        else:
            log_msg += "NPCの勝ち！"

    updated_state = replace(
        state, current_battle=new_res, battle_log=state.battle_log + [log_msg]
    )

    for side, debuff in state.pending_conditional_debuff_on_loss:
        side_lost = (side == Side.PLAYER and winning_side == Side.NPC) or (
            side == Side.NPC and winning_side == Side.PLAYER
        )
        if not side_lost:
            continue

        if side == Side.PLAYER:
            updated_state = replace(
                updated_state,
                npc=replace(
                    updated_state.npc,
                    next_round_conditional_point_modifier_non_wildcard=(
                        updated_state.npc.next_round_conditional_point_modifier_non_wildcard
                        + debuff
                    ),
                ),
                battle_log=updated_state.battle_log
                + [
                    f"効果発動: 敗北したため相手の次ラウンド(バー以外)ポイント{debuff:+d}"
                ],
            )
        else:
            updated_state = replace(
                updated_state,
                player=replace(
                    updated_state.player,
                    next_round_conditional_point_modifier_non_wildcard=(
                        updated_state.player.next_round_conditional_point_modifier_non_wildcard
                        + debuff
                    ),
                ),
                battle_log=updated_state.battle_log
                + [
                    f"効果発動: 敗北したため相手の次ラウンド(バー以外)ポイント{debuff:+d}"
                ],
            )

    for side, draw_count in state.pending_draw_on_win:
        if side != winning_side:
            continue

        if side == Side.PLAYER:
            drawn = updated_state.player.deck[:draw_count]
            updated_state = replace(
                updated_state,
                player=replace(
                    updated_state.player,
                    hand=updated_state.player.hand + drawn,
                    deck=updated_state.player.deck[len(drawn) :],
                ),
                battle_log=updated_state.battle_log
                + [f"効果発動: 勝利したため{len(drawn)}枚ドロー"],
            )
        else:
            drawn = updated_state.npc.deck[:draw_count]
            updated_state = replace(
                updated_state,
                npc=replace(
                    updated_state.npc,
                    hand=updated_state.npc.hand + drawn,
                    deck=updated_state.npc.deck[len(drawn) :],
                ),
                battle_log=updated_state.battle_log
                + [f"効果発動: 勝利したため{len(drawn)}枚ドロー"],
            )

    for side, bonus in state.pending_next_round_buff_on_win:
        if side != winning_side:
            continue

        if side == Side.PLAYER:
            updated_state = replace(
                updated_state,
                player=replace(
                    updated_state.player,
                    next_round_point_modifier=(
                        updated_state.player.next_round_point_modifier + bonus
                    ),
                ),
                battle_log=updated_state.battle_log
                + [f"効果発動: 勝利したため次ラウンドのポイント{bonus:+d}"],
            )
        else:
            updated_state = replace(
                updated_state,
                npc=replace(
                    updated_state.npc,
                    next_round_point_modifier=(
                        updated_state.npc.next_round_point_modifier + bonus
                    ),
                ),
                battle_log=updated_state.battle_log
                + [f"効果発動: 勝利したため次ラウンドのポイント{bonus:+d}"],
            )

    return updated_state
