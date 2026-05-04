import random
from dataclasses import replace

from shadow_bout.effect_handlers.common import (
    JANKEN_NAMES,
    _find_card,
    _find_card_by_id,
    _finish_interactive_effect,
    _opponent_is_immune,
    _remove_first_card_by_id,
)
from shadow_bout.effect_utils import (
    get_opponent_side,
    get_player_state,
    update_player,
)
from shadow_bout.models import GameState, Janken, Phase, Side


def _coerce_declared_janken(choice: str | None) -> Janken:
    if choice is None:
        return Janken.ROCK
    try:
        janken = Janken(choice)
    except ValueError:
        return Janken.ROCK
    if janken not in (Janken.ROCK, Janken.SCISSORS, Janken.PAPER):
        return Janken.ROCK
    return janken


def _resume_special(state: GameState, side: Side, choice: str | None) -> GameState:
    ctx = state.pending_effect_context
    source_card = _find_card_by_id(state, side, ctx.card_id if ctx else None)
    source_name = source_card.name if source_card else "美希"
    opp_side = get_opponent_side(side)
    opp_state = get_player_state(state, opp_side)

    if ctx and ctx.step == 1:
        target = _find_card(opp_state.won_cards, choice) or (
            opp_state.won_cards[0] if opp_state.won_cards else None
        )
        if target is None:
            return _finish_interactive_effect(
                state, f"-> {source_name}の効果: 相手の勝ち札がないため奪取できない"
            )

        own_state = get_player_state(state, side)
        state = update_player(state, side, deck=own_state.deck + [target])
        state = update_player(
            state,
            opp_side,
            won_cards=_remove_first_card_by_id(opp_state.won_cards, target.id),
        )
        return _finish_interactive_effect(
            state,
            f"-> {source_name}の効果: {target.name}を相手の勝ち札から奪い、自分の山札の下へ置いた",
        )

    declared = _coerce_declared_janken(choice)
    declared_name = JANKEN_NAMES[declared]
    if not opp_state.hand:
        return _finish_interactive_effect(
            state,
            f"-> {source_name}の効果: {declared_name}を宣言したが、相手の手札がないため確認できない",
        )

    revealed = random.choice(opp_state.hand)
    revealed_name = JANKEN_NAMES.get(revealed.janken, revealed.janken.value)
    log = (
        f"-> {source_name}の効果: {declared_name}を宣言し、"
        f"相手手札から{revealed.name}({revealed_name})を確認"
    )
    if revealed.janken != declared:
        return _finish_interactive_effect(state, f"{log}。一致しないため奪取なし")

    if not opp_state.won_cards:
        return _finish_interactive_effect(
            state, f"{log}。一致したが相手の勝ち札がないため奪取できない"
        )

    next_ctx = replace(
        ctx,
        step=1,
        payload={
            **(ctx.payload if ctx else {}),
            "declared_janken": declared.value,
            "revealed_card_id": revealed.id,
        },
    )
    return replace(
        state,
        phase=Phase.INTERACTIVE_EFFECT,
        pending_effect_context=next_ctx,
        battle_log=state.battle_log + [f"{log}。奪取する勝ち札を選択中..."],
    )


def _resume_removal(state: GameState, side: Side, choice: str | None) -> GameState:
    if choice not in (None, "activate", "yes", "true"):
        return _finish_interactive_effect(state, "-> ジュリアの効果: 発動しない")

    ctx = state.pending_effect_context
    source_card = _find_card_by_id(state, side, ctx.card_id if ctx else None)
    if source_card and _opponent_is_immune(state, side):
        return _finish_interactive_effect(
            state, f"-> {source_card.name}の効果: 相手は戦具効果を受けないため不発"
        )

    res = state.current_battle
    if side == Side.PLAYER:
        own_state = state.player
        opp_state = state.npc
        state = replace(
            state,
            player=replace(own_state, deck=own_state.deck + [res.player_card]),
            npc=replace(opp_state, discard=opp_state.discard + [res.npc_card]),
        )
    else:
        own_state = state.npc
        opp_state = state.player
        state = replace(
            state,
            npc=replace(own_state, deck=own_state.deck + [res.npc_card]),
            player=replace(opp_state, discard=opp_state.discard + [res.player_card]),
        )

    state = replace(state, removal_activated=True)
    return _finish_interactive_effect(state, "-> ジュリアの効果: 勝敗判定をスキップ")
