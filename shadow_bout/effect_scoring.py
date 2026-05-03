from dataclasses import replace

from shadow_bout.models import (
    Card,
    GameState,
    Janken,
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


def resolve_post_effect_skipped(state: GameState) -> GameState:
    # Julia's removal effect already moved the cards, so the round is consumed
    # without applying the normal win/loss card movement.
    res = state.current_battle
    new_res = replace(res, outcome=RoundOutcome.EVEN, winning_side=None)
    return replace(state, phase=Phase.REVEAL, current_battle=new_res)


def resolve_post_effect_points(state: GameState) -> GameState:
    res = state.current_battle
    p_point = calculate_effective_point(res.player_card, state.player)
    n_point = calculate_effective_point(res.npc_card, state.npc)

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
        player_point=p_point,
        npc_point=n_point,
    )

    log_msg = f"効果解決後ポイント比較: あなた({p_point}) vs NPC({n_point}) -> "
    if outcome == RoundOutcome.WIN:
        log_msg += "あなたの勝ち！"
    elif outcome == RoundOutcome.LOSE:
        log_msg += "NPCの勝ち！"
    else:
        log_msg += "引き分け！"

    updated_state = replace(
        state, current_battle=new_res, battle_log=state.battle_log + [log_msg]
    )

    # card_18: この勝負に負けた場合、次の勝負で相手-3（バー以外）
    if res.player_card.id == "card_18" and winning_side == Side.NPC:
        updated_state = replace(
            updated_state,
            npc=replace(
                updated_state.npc,
                next_round_conditional_point_modifier_non_wildcard=(
                    updated_state.npc.next_round_conditional_point_modifier_non_wildcard
                    + int(res.player_card.effect.value or 0)
                ),
            ),
            battle_log=updated_state.battle_log
            + [
                f"{res.player_card.name}の効果発動: 敗北したため相手の次ラウンド(バー以外)ポイント{int(res.player_card.effect.value or 0):+d}"
            ],
        )
    elif res.npc_card.id == "card_18" and winning_side == Side.PLAYER:
        updated_state = replace(
            updated_state,
            player=replace(
                updated_state.player,
                next_round_conditional_point_modifier_non_wildcard=(
                    updated_state.player.next_round_conditional_point_modifier_non_wildcard
                    + int(res.npc_card.effect.value or 0)
                ),
            ),
            battle_log=updated_state.battle_log
            + [
                f"{res.npc_card.name}の効果発動: 敗北したため相手の次ラウンド(バー以外)ポイント{int(res.npc_card.effect.value or 0):+d}"
            ],
        )

    return updated_state
