from dataclasses import replace

from shadow_bout.models import Card, GameState, Phase, PlayerState, RoundOutcome, Side


def calculate_effective_point(card: Card, player_state: PlayerState) -> int:
    return card.base_point + player_state.point_modifier


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

    return replace(
        state, current_battle=new_res, battle_log=state.battle_log + [log_msg]
    )
