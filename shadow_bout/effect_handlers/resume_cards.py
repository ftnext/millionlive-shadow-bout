import random
from dataclasses import replace

from shadow_bout.effect_handlers.common import (
    _find_card,
    _find_card_by_id,
    _finish_interactive_effect,
    _parse_card_ids,
)
from shadow_bout.effect_utils import (
    get_opponent_side,
    get_player_state,
    is_immune_to_opponent_effect,
    update_player,
)
from shadow_bout.models import Card, GameState, Side


def _resume_search_and_swap(
    state: GameState, side: Side, choice: str | None
) -> GameState:
    if not choice or ":" not in choice:
        return _finish_interactive_effect(state, "-> 千鶴の効果: 交換しない")

    hand_id, deck_id = choice.split(":", 1)
    p_state = get_player_state(state, side)
    hand_card = _find_card(p_state.hand, hand_id)
    deck_card = _find_card(p_state.deck, deck_id)
    if hand_card is None or deck_card is None:
        return _finish_interactive_effect(state, "-> 千鶴の効果: 交換しない")

    new_hand = [deck_card if card.id == hand_card.id else card for card in p_state.hand]
    new_deck = [hand_card if card.id == deck_card.id else card for card in p_state.deck]
    state = update_player(state, side, hand=new_hand, deck=new_deck)
    return _finish_interactive_effect(
        state, f"-> 千鶴の効果: {hand_card.name}と{deck_card.name}を交換"
    )


def _resume_swap(state: GameState, side: Side, choice: str | None) -> GameState:
    p_state = get_player_state(state, side)
    target = _find_card(p_state.hand, choice)
    if target is None:
        return _finish_interactive_effect(state, "-> 真の効果: 入れ替えない")

    res = state.current_battle
    if side == Side.PLAYER:
        old_card = res.player_card
        new_res = replace(res, player_card=target)
    else:
        old_card = res.npc_card
        new_res = replace(res, npc_card=target)

    new_hand = [card for card in p_state.hand if card.id != target.id] + [old_card]
    state = update_player(state, side, hand=new_hand)
    state = replace(state, current_battle=new_res)
    return _finish_interactive_effect(
        state, f"-> 真の効果: {old_card.name}と{target.name}を入れ替え"
    )


def _resume_tutor_play(state: GameState, side: Side, choice: str | None) -> GameState:
    if choice in (None, "", "skip"):
        return _finish_interactive_effect(state, "-> 麗花の効果: 発動しない")

    p_state = get_player_state(state, side)
    res = state.current_battle
    if res is None:
        return _finish_interactive_effect(
            state, "-> 麗花の効果: 場のカードがないため不発"
        )

    old_card = res.player_card if side == Side.PLAYER else res.npc_card
    target = _find_card(p_state.deck, choice)

    if choice == old_card.id:
        new_deck = list(p_state.deck)
        random.shuffle(new_deck)
        state = update_player(state, side, deck=new_deck)
        return _finish_interactive_effect(
            state, f"-> 麗花の効果: {old_card.name}を場に出し直し、山札を切った"
        )

    if target is None:
        return _finish_interactive_effect(state, "-> 麗花の効果: 発動しない")

    if side == Side.PLAYER:
        new_res = replace(res, player_card=target)
    else:
        new_res = replace(res, npc_card=target)

    new_deck = [card for card in p_state.deck if card.id != target.id] + [old_card]
    random.shuffle(new_deck)
    state = update_player(state, side, deck=new_deck)
    state = replace(state, current_battle=new_res)
    return _finish_interactive_effect(
        state, f"-> 麗花の効果: {old_card.name}を山札に戻し、{target.name}を場に出した"
    )


def _resume_swap_opponent(
    state: GameState, side: Side, choice: str | None
) -> GameState:
    ctx = state.pending_effect_context
    opp_side = get_opponent_side(side)
    source_card = _find_card_by_id(state, side, ctx.card_id if ctx else None)
    if source_card and is_immune_to_opponent_effect(state, side, opp_side):
        return _finish_interactive_effect(
            state, f"-> {source_card.name}の効果: 相手は戦具効果を受けないため不発"
        )

    opp_state = get_player_state(state, opp_side)
    if not opp_state.hand:
        return _finish_interactive_effect(
            state, "-> 可奈の効果: 相手の手札がないため入れ替えられない"
        )
    if ctx and ctx.step == 0:
        target = random.choice(opp_state.hand)
        next_ctx = replace(ctx, step=1, payload={**ctx.payload, "target_id": target.id})
        return replace(
            state,
            pending_effect_context=next_ctx,
            battle_log=state.battle_log
            + [f"-> 可奈の効果: 相手手札から{target.name}を確認した"],
        )

    target = _find_card(opp_state.hand, ctx.payload.get("target_id") if ctx else None)
    if target is None:
        return _finish_interactive_effect(
            state, "-> 可奈の効果: 確認したカードが手札にないため入れ替えない"
        )
    if choice != "swap":
        return _finish_interactive_effect(state, "-> 可奈の効果: 入れ替えない")
    res = state.current_battle
    if opp_side == Side.PLAYER:
        old_card = res.player_card
        new_res = replace(res, player_card=target)
    else:
        old_card = res.npc_card
        new_res = replace(res, npc_card=target)

    new_opp_hand = [card for card in opp_state.hand if card.id != target.id] + [
        old_card
    ]
    state = update_player(state, opp_side, hand=new_opp_hand)
    state = replace(state, current_battle=new_res)
    return _finish_interactive_effect(
        state,
        f"-> 可奈の効果: 相手手札を確認し、{old_card.name}と{target.name}を入れ替え",
    )


def _resume_salvage(state: GameState, side: Side, choice: str | None) -> GameState:
    p_state = get_player_state(state, side)
    if not p_state.discard:
        return _finish_interactive_effect(state, "-> 風花の効果: 回収できる捨札がない")

    target = _find_card(p_state.discard, choice)
    if target is None:
        return _finish_interactive_effect(state, "-> 風花の効果: 回収しない")

    ctx = state.pending_effect_context
    source_card = _find_card_by_id(state, side, ctx.card_id if ctx else None)
    penalty = int(
        source_card.effect.value if source_card and source_card.effect else -3
    )
    new_discard = [card for card in p_state.discard if card.id != target.id]
    state = update_player(
        state,
        side,
        hand=p_state.hand + [target],
        discard=new_discard,
        point_modifier=p_state.point_modifier + penalty,
    )
    return _finish_interactive_effect(
        state, f"-> 風花の効果: {target.name}を回収し、ポイント{penalty}"
    )


def _resume_reorder(state: GameState, side: Side, choice: str | None) -> GameState:
    opponent_side = get_opponent_side(side)
    opponent_state = get_player_state(state, opponent_side)
    if not opponent_state.deck:
        return _finish_interactive_effect(
            state, "-> 茜の効果: 並び替える相手の山札がない"
        )

    selected_ids = _parse_card_ids(choice)
    ordered: list[Card] = []
    used_ids: set[str] = set()
    for card_id in selected_ids:
        card = _find_card(opponent_state.deck, card_id)
        if card is None or card.id in used_ids:
            continue
        ordered.append(card)
        used_ids.add(card.id)

    ordered.extend(card for card in opponent_state.deck if card.id not in used_ids)
    state = update_player(state, opponent_side, deck=ordered)
    return _finish_interactive_effect(state, "-> 茜の効果: 相手の山札の順番を入れ替えた")
