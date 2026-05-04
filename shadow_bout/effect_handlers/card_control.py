import random
from dataclasses import replace

from shadow_bout.effect_handlers.common import (
    JANKEN_NAMES,
    _immune_blocked_state,
    _opponent_is_immune,
)
from shadow_bout.effect_handlers.registry import register
from shadow_bout.effect_utils import (
    add_banned_card_id,
    clear_forced_card_id,
    get_opponent_side,
    get_player_state,
    set_must_reveal_played_card,
    update_player,
)
from shadow_bout.models import (
    Card,
    GameState,
    Janken,
    Phase,
    Side,
)


@register("win_condition")
def effect_win_condition(state: GameState, side: Side, card: Card) -> GameState:
    own_state = get_player_state(state, side)
    opp_side = get_opponent_side(side)
    opp_state = get_player_state(state, opp_side)

    own_top = own_state.deck[0] if own_state.deck else None
    opp_top = opp_state.deck[0] if opp_state.deck else None

    if own_top is not None:
        state = update_player(state, side, deck=own_state.deck[1:] + [own_top])
    if opp_top is not None:
        state = update_player(state, opp_side, deck=opp_state.deck[1:] + [opp_top])

    if own_top is None or opp_top is None:
        return replace(
            state,
            battle_log=state.battle_log
            + [f"{card.name}の効果発動: 山札が不足しているため不発"],
        )

    revealed_jankens = {own_top.janken, opp_top.janken}
    reveal_log = (
        f"{card.name}の効果発動: 山札の上から自分は{own_top.name}"
        f"({JANKEN_NAMES.get(own_top.janken, own_top.janken.value)})、"
        f"相手は{opp_top.name}"
        f"({JANKEN_NAMES.get(opp_top.janken, opp_top.janken.value)})"
        "を公開し山札の下へ戻した"
    )

    if revealed_jankens == {Janken.PAPER, Janken.SCISSORS}:
        return replace(
            state,
            win_condition_winner=side,
            battle_log=state.battle_log + [f"{reveal_log}。勝利条件成立"],
        )

    return replace(
        state,
        battle_log=state.battle_log + [f"{reveal_log}。勝利条件不成立"],
    )


@register("force_play")
def effect_force_play(state: GameState, side: Side, card: Card) -> GameState:
    opp_side = get_opponent_side(side)
    if _opponent_is_immune(state, side):
        return _immune_blocked_state(state, card)

    opp_state = get_player_state(state, opp_side)
    if not opp_state.hand:
        return replace(
            state,
            battle_log=state.battle_log
            + [f"{card.name}の効果発動: 相手の手札がないため不発"],
        )

    target = random.choice(opp_state.hand)
    state = update_player(state, opp_side, forced_card_id=target.id)
    return replace(
        state,
        battle_log=state.battle_log
        + [f"{card.name}の効果発動: 相手は次ラウンドで{target.name}を強制プレイ"],
    )


@register("ban")
def effect_ban(state: GameState, side: Side, card: Card) -> GameState:
    opp_side = get_opponent_side(side)
    if _opponent_is_immune(state, side):
        return _immune_blocked_state(state, card)

    opp_state = get_player_state(state, opp_side)
    if not opp_state.hand:
        return replace(
            state,
            battle_log=state.battle_log
            + [f"{card.name}の効果発動: 相手の手札がないため不発"],
        )

    target = random.choice(opp_state.hand)
    state = add_banned_card_id(state, opp_side, target.id)

    if opp_state.forced_card_id == target.id:
        state = clear_forced_card_id(state, opp_side)
        return replace(
            state,
            battle_log=state.battle_log
            + [
                f"{card.name}の効果発動: 相手の{target.name}を使用禁止（強制プレイは解除）"
            ],
        )

    return replace(
        state,
        battle_log=state.battle_log
        + [f"{card.name}の効果発動: 相手の{target.name}を使用禁止"],
    )


@register("reveal")
def effect_reveal(state: GameState, side: Side, card: Card) -> GameState:
    opp_side = get_opponent_side(side)
    if _opponent_is_immune(state, side):
        return _immune_blocked_state(state, card)

    opp_state = get_player_state(state, opp_side)
    if not opp_state.hand:
        return state

    target = random.choice(opp_state.hand)
    new_revealed = opp_state.revealed_card_ids | {target.id}
    state = update_player(state, opp_side, revealed_card_ids=new_revealed)
    return replace(
        state,
        battle_log=state.battle_log
        + [f"{card.name}の効果発動: 相手の手札を1枚永続公開"],
    )


@register("reveal_all")
def effect_reveal_all(state: GameState, side: Side, card: Card) -> GameState:
    opp_side = get_opponent_side(side)
    if _opponent_is_immune(state, side):
        return _immune_blocked_state(state, card)

    opp_state = get_player_state(state, opp_side)
    new_revealed = opp_state.revealed_card_ids | {
        hand_card.id for hand_card in opp_state.hand
    }
    state = update_player(state, opp_side, revealed_card_ids=new_revealed)

    state = replace(
        state,
        revealed_this_round=list(opp_state.hand),
        revealed_this_round_side=opp_side,
    )
    return replace(
        state,
        battle_log=state.battle_log + [f"{card.name}の効果発動: 相手の手札を全て公開"],
    )


@register("restart")
def effect_restart(state: GameState, side: Side, card: Card) -> GameState:
    if _opponent_is_immune(state, side):
        return _immune_blocked_state(state, card)

    if state.last_restart_round == state.round_number - 1:
        return replace(
            state,
            battle_log=state.battle_log
            + [f"{card.name}の効果発動: 連続使用不可のため不発"],
        )

    state = replace(
        state,
        battle_log=state.battle_log + [f"{card.name}の効果発動: この勝負をやり直す"],
    )

    res = state.current_battle
    p_card = res.player_card
    n_card = res.npc_card

    new_p_hand = state.player.hand + [p_card]
    new_n_hand = state.npc.hand + [n_card]

    state = update_player(state, Side.PLAYER, hand=new_p_hand)
    state = update_player(state, Side.NPC, hand=new_n_hand)

    state = update_player(state, Side.PLAYER, point_modifier=0, effect_negated=False)
    state = update_player(state, Side.NPC, point_modifier=0, effect_negated=False)

    return replace(
        state,
        phase=Phase.SELECT,
        current_battle=None,
        effect_queue=[],
        last_restart_round=state.round_number,
        pending_conditional_debuff_on_loss=(),
        pending_draw_on_win=(),
        pending_next_round_buff_on_win=(),
        point_match_effects=(),
        battle_janken_overrides=(),
        win_condition_winner=None,
    )


@register("curse")
def effect_curse(state: GameState, side: Side, card: Card) -> GameState:
    opp_side = get_opponent_side(side)
    if _opponent_is_immune(state, side):
        return _immune_blocked_state(state, card)

    state = set_must_reveal_played_card(state, opp_side, True)
    return replace(
        state,
        battle_log=state.battle_log
        + [f"{card.name}の効果発動: 相手の次の出し札を公開"],
    )
