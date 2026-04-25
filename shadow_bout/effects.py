import random
from dataclasses import replace
from typing import Callable

from shadow_bout.models import (
    Card,
    GameState,
    Phase,
    PlayerState,
    RoundOutcome,
    Side,
)

EffectHandler = Callable[[GameState, Side, Card], GameState]
_registry: dict[str, EffectHandler] = {}


def register(effect_type: str):
    def decorator(fn: EffectHandler):
        _registry[effect_type] = fn
        return fn

    return decorator


def update_player(state: GameState, side: Side, **kwargs) -> GameState:
    if side == Side.PLAYER:
        new_p = replace(state.player, **kwargs)
        return replace(state, player=new_p)
    else:
        new_n = replace(state.npc, **kwargs)
        return replace(state, npc=new_n)


def get_player_state(state: GameState, side: Side) -> PlayerState:
    return state.player if side == Side.PLAYER else state.npc


def get_opponent_side(side: Side) -> Side:
    return Side.NPC if side == Side.PLAYER else Side.PLAYER


def calculate_effective_point(card: Card, player_state: PlayerState) -> int:
    return card.base_point + len(player_state.hand) + player_state.point_modifier


def init_effect_resolution(state: GameState, p_card: Card, n_card: Card) -> GameState:
    # Sort order: smaller base_point first, then kana.
    cards = [(Side.PLAYER, p_card), (Side.NPC, n_card)]
    cards.sort(key=lambda x: (x[1].base_point, x[1].kana))

    return replace(state, effect_queue=cards, phase=Phase.EFFECT_RESOLUTION)


def process_next_effect(state: GameState) -> GameState:
    # Check if a nested effect was just resolved (return from copy_hand)
    # The stack is represented in pending_effect_context if needed, but for simplicity,
    # we just consume from effect_queue.

    if state.phase == Phase.INTERACTIVE_EFFECT:
        return state

    current_state = state
    while current_state.effect_queue and current_state.phase == Phase.EFFECT_RESOLUTION:
        if current_state.removal_activated:
            current_state = replace(current_state, effect_queue=[])
            break

        side, card = current_state.effect_queue[0]

        # Check negate flag
        p_state = get_player_state(current_state, side)
        if p_state.effect_negated:
            # Skip this effect
            current_state = replace(
                current_state, effect_queue=current_state.effect_queue[1:]
            )
            continue

        if not card.effect or card.effect.type.value not in _registry:
            # No effect or unknown effect
            current_state = replace(
                current_state, effect_queue=current_state.effect_queue[1:]
            )
            continue

        handler = _registry[card.effect.type.value]

        # We pop before applying, so that if interactive, it's considered popped
        # Wait, if it's interactive, we shouldn't pop? Or we pop and store in pending_effect_context.
        # Let's pop it now, and if it's interactive, it sets phase = INTERACTIVE_EFFECT.
        popped_queue = current_state.effect_queue[1:]
        current_state = replace(current_state, effect_queue=popped_queue)

        current_state = handler(current_state, side, card)

        if current_state.phase == Phase.INTERACTIVE_EFFECT:
            break

    # If queue is empty and we are not interactive, transition to points comparison (or skip if removal)
    if (
        not current_state.effect_queue
        and current_state.phase == Phase.EFFECT_RESOLUTION
    ):
        if current_state.removal_activated:
            current_state = resolve_post_effect_skipped(current_state)
        else:
            current_state = resolve_post_effect_points(current_state)

    return current_state


def resume_effect(state: GameState, choice: str | None = None) -> GameState:
    # MVP Implementation: Just acknowledge the interactive effect and continue.
    # In full implementation, this would process the choice and apply it.
    ctx = state.pending_effect_context
    if ctx:
        state = replace(
            state, battle_log=state.battle_log + ["-> 選択完了 (MVP自動処理)"]
        )
        state = replace(
            state, phase=Phase.EFFECT_RESOLUTION, pending_effect_context=None
        )
    return process_next_effect(state)


def resolve_post_effect_skipped(state: GameState) -> GameState:
    # Julia's effect activated. Round is consumed, no win/loss.
    # We add a log and go to REVEAL, but current_battle must be handled specially.
    res = state.current_battle
    new_res = replace(res, outcome=RoundOutcome.EVEN, winning_side=None)
    # We must not add the cards to draw_stock because Julia returns to deck and opponent to discard.
    # The card movement is already handled in the removal effect handler!
    # So we just proceed to next round phase-wise.
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


@register("null")
def effect_null(state: GameState, side: Side, card: Card) -> GameState:
    return state


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


@register("negate")
def effect_negate(state: GameState, side: Side, card: Card) -> GameState:
    opp_side = get_opponent_side(side)
    state = update_player(state, opp_side, effect_negated=True)
    return replace(
        state,
        battle_log=state.battle_log
        + [f"{card.name}の効果発動: 相手の戦具効果を無効化"],
    )


@register("reveal")
def effect_reveal(state: GameState, side: Side, card: Card) -> GameState:
    opp_side = get_opponent_side(side)
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
    opp_state = get_player_state(state, opp_side)

    state = replace(state, revealed_this_round=list(opp_state.hand))
    return replace(
        state,
        battle_log=state.battle_log + [f"{card.name}の効果発動: 相手の手札を一時確認"],
    )


@register("restart")
def effect_restart(state: GameState, side: Side, card: Card) -> GameState:
    # "この効果は連続で使用することはできない"
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

    # Return cards to hand
    new_p_hand = state.player.hand + [p_card]
    new_n_hand = state.npc.hand + [n_card]

    state = update_player(state, Side.PLAYER, hand=new_p_hand)
    state = update_player(state, Side.NPC, hand=new_n_hand)

    # Reset round state but increment round_number? The plan says "この勝負をやり直す"
    # Actually, restart implies doing the SAME round again.
    # So we set phase back to SELECT, clear current_battle.
    # Also reset point modifiers and negated flags? Yes, for the new round.
    state = update_player(state, Side.PLAYER, point_modifier=0, effect_negated=False)
    state = update_player(state, Side.NPC, point_modifier=0, effect_negated=False)

    return replace(
        state,
        phase=Phase.SELECT,
        current_battle=None,
        effect_queue=[],
        last_restart_round=state.round_number,
    )


@register("choose")
def effect_choose(state: GameState, side: Side, card: Card) -> GameState:
    ctx = {"side": side.value, "card_id": card.id, "effect": "choose"}
    state = replace(
        state, phase=Phase.INTERACTIVE_EFFECT, effect_step=0, pending_effect_context=ctx
    )
    return replace(
        state, battle_log=state.battle_log + [f"{card.name}の効果発動: 選択待機中..."]
    )


@register("copy_hand")
def effect_copy_hand(state: GameState, side: Side, card: Card) -> GameState:
    p_state = get_player_state(state, side)
    if not p_state.hand:
        return state

    ctx = {"side": side.value, "card_id": card.id, "effect": "copy_hand"}
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
    elif top_card.effect and top_card.effect.type.value in _registry:
        # Prepend to effect queue to execute it right away
        new_queue = [(side, top_card)] + state.effect_queue
        return replace(state, effect_queue=new_queue)

    return state


@register("search_and_swap")
def effect_search_and_swap(state: GameState, side: Side, card: Card) -> GameState:
    ctx = {"side": side.value, "card_id": card.id, "effect": "search_and_swap"}
    state = replace(
        state, phase=Phase.INTERACTIVE_EFFECT, effect_step=0, pending_effect_context=ctx
    )
    return replace(
        state,
        battle_log=state.battle_log + [f"{card.name}の効果発動: 交換選択待機中..."],
    )


@register("swap")
def effect_swap(state: GameState, side: Side, card: Card) -> GameState:
    ctx = {"side": side.value, "card_id": card.id, "effect": "swap"}
    state = replace(
        state, phase=Phase.INTERACTIVE_EFFECT, effect_step=0, pending_effect_context=ctx
    )
    return replace(
        state,
        battle_log=state.battle_log + [f"{card.name}の効果発動: 入れ替え選択待機中..."],
    )


@register("removal")
def effect_removal(state: GameState, side: Side, card: Card) -> GameState:
    ctx = {"side": side.value, "card_id": card.id, "effect": "removal"}
    state = replace(
        state, phase=Phase.INTERACTIVE_EFFECT, effect_step=0, pending_effect_context=ctx
    )
    return replace(
        state, battle_log=state.battle_log + [f"{card.name}の効果発動: 発動待機中..."]
    )
