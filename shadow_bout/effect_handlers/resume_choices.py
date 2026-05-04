from dataclasses import replace

from shadow_bout.effect_handlers.common import (
    _find_card,
    _find_card_by_id,
    _finish_interactive_effect,
    _opponent_is_immune,
    _parse_card_ids,
)
from shadow_bout.effect_handlers.registry import get_effect_handler
from shadow_bout.effect_utils import (
    get_opponent_side,
    get_player_state,
    set_must_reveal_played_card_rounds,
    update_player,
)
from shadow_bout.models import GameState, Phase, PointMatchEffect, Side


def _resume_choose(state: GameState, side: Side, choice: str | None) -> GameState:
    ctx = state.pending_effect_context
    if ctx is None:
        return state
    p_state = get_player_state(state, side)
    variant = ctx.payload.get("choose_variant")
    if variant in ("yuriko_choose", "yuriko_return_cards"):
        if ctx.step == 1:
            return_count = int(ctx.payload.get("return_count", 0))
            selected_ids = _parse_card_ids(choice)
            returned = [
                card
                for card_id in selected_ids
                if (card := _find_card(p_state.hand, card_id))
            ][:return_count]

            if len(returned) < return_count:
                returned_ids = {card.id for card in returned}
                returned.extend(
                    card for card in p_state.hand if card.id not in returned_ids
                )
                returned = returned[:return_count]

            returned_ids = {card.id for card in returned}
            new_hand = [card for card in p_state.hand if card.id not in returned_ids]
            new_deck = p_state.deck + returned
            state = update_player(state, side, hand=new_hand, deck=new_deck)
            return _finish_interactive_effect(
                state,
                "-> 百合子の効果: 山札から2枚引き、2枚を山札の下へ戻した",
            )

        if choice == "draw_cards":
            drawn = p_state.deck[:2]
            new_deck = p_state.deck[2:]
            new_hand = p_state.hand + drawn
            state = update_player(state, side, hand=new_hand, deck=new_deck)
            return_count = min(2, len(new_hand))
            if return_count == 0:
                return _finish_interactive_effect(
                    state,
                    "-> 百合子の効果: 山札からカードを引けず、戻す手札もなかった",
                )

            next_ctx = replace(
                ctx,
                step=1,
                payload={
                    "choose_variant": "yuriko_return_cards",
                    "return_count": return_count,
                    "drawn_ids": [c.id for c in drawn],
                },
            )
            return replace(
                state,
                phase=Phase.INTERACTIVE_EFFECT,
                pending_effect_context=next_ctx,
                battle_log=state.battle_log
                + [
                    f"-> 百合子の効果: 山札から{len(drawn)}枚引いた。戻す手札を選択中..."
                ],
            )

        state = update_player(state, side, point_modifier=p_state.point_modifier + 3)
        return _finish_interactive_effect(state, "-> 百合子の効果: ポイント+3")

    if variant == "karen_choose":
        if choice != "activate":
            return _finish_interactive_effect(state, "-> 可憐の効果: 発動しない")
        if _opponent_is_immune(state, side):
            return _finish_interactive_effect(
                state, "-> 可憐の効果: 相手は戦具効果を受けないため不発"
            )
        opp_side = get_opponent_side(side)
        state = set_must_reveal_played_card_rounds(state, opp_side, rounds=2)
        return _finish_interactive_effect(
            state, "-> 可憐の効果: 相手は2ラウンドの間、出し札を公開"
        )

    return _finish_interactive_effect(state, "-> 選択効果: 未対応カード")


def _resume_choose_multiple(
    state: GameState, side: Side, choice: str | None
) -> GameState:
    p_state = get_player_state(state, side)
    if not choice:
        return replace(
            state,
            battle_log=state.battle_log
            + ["-> 海美の効果: 効果を1つ以上選択してください"],
        )

    selected = set(_parse_card_ids(choice))

    can_discard = bool(p_state.hand)
    can_draw = bool(p_state.deck)

    do_discard = "discard_buff" in selected and can_discard
    do_draw = "draw_debuff" in selected and can_draw

    if not do_discard and not do_draw:
        return _finish_interactive_effect(state, "-> 海美の効果: 発動可能な効果がない")

    logs: list[str] = []

    if do_discard:
        discarded = p_state.hand[0]
        p_state = replace(
            p_state,
            hand=p_state.hand[1:],
            discard=p_state.discard + [discarded],
            point_modifier=p_state.point_modifier + 5,
        )
        logs.append(f"{discarded.name}を捨札にしてポイント+5")

    if do_draw:
        drawn = p_state.deck[0]
        p_state = replace(
            p_state,
            hand=p_state.hand + [drawn],
            deck=p_state.deck[1:],
            point_modifier=p_state.point_modifier - 2,
        )
        logs.append(f"{drawn.name}を1枚引いてポイント-2")

    state = update_player(
        state,
        side,
        hand=p_state.hand,
        deck=p_state.deck,
        discard=p_state.discard,
        point_modifier=p_state.point_modifier,
    )
    return _finish_interactive_effect(state, f"-> 海美の効果: {'、'.join(logs)}")


def _resume_copy_hand(state: GameState, side: Side, choice: str | None) -> GameState:
    p_state = get_player_state(state, side)
    target = _find_card(p_state.hand, choice) or (
        p_state.hand[0] if p_state.hand else None
    )
    if (
        target is None
        or not target.effect
        or get_effect_handler(target.effect.type.value) is None
    ):
        return _finish_interactive_effect(state, "-> 杏奈の効果: 発動できる手札なし")

    state = _finish_interactive_effect(
        state, f"-> 杏奈の効果: {target.name}の効果を発動"
    )
    return replace(state, effect_queue=[(side, target)] + state.effect_queue)


def _resume_debuff_counterable(
    state: GameState, side: Side, choice: str | None
) -> GameState:
    ctx = state.pending_effect_context
    source_side = get_opponent_side(side)
    source_card = _find_card_by_id(state, source_side, ctx.card_id if ctx else None)
    source_name = source_card.name if source_card else "志保"
    debuff = int(
        source_card.effect.value
        if source_card and source_card.effect
        else (ctx.payload.get("debuff", -5) if ctx else -5)
    )

    p_state = get_player_state(state, side)
    discard_target = None
    if choice == "counter":
        discard_target = p_state.hand[0] if p_state.hand else None
    elif choice not in (None, "", "skip", "no_counter"):
        discard_target = _find_card(p_state.hand, choice)

    if discard_target is None:
        state = update_player(
            state,
            side,
            point_modifier=p_state.point_modifier + debuff,
        )
        return _finish_interactive_effect(
            state,
            f"-> {source_name}の効果: 相手が無効化せず、相手のポイント{debuff:+d}",
        )

    state = update_player(
        state,
        side,
        hand=[card for card in p_state.hand if card.id != discard_target.id],
        discard=p_state.discard + [discard_target],
    )
    return _finish_interactive_effect(
        state,
        f"-> {source_name}の効果: 相手は{discard_target.name}を捨札にして無効化",
    )


def _resume_set_point_match(
    state: GameState, side: Side, choice: str | None
) -> GameState:
    ctx = state.pending_effect_context
    source_card = _find_card_by_id(state, side, ctx.card_id if ctx else None)
    source_name = source_card.name if source_card else "歩"

    if choice != "activate":
        return _finish_interactive_effect(state, f"-> {source_name}の効果: 発動しない")

    if _opponent_is_immune(state, side):
        return _finish_interactive_effect(
            state, f"-> {source_name}の効果: 相手は戦具効果を受けないため不発"
        )

    effect = PointMatchEffect(
        source_side=side,
        target_side=get_opponent_side(side),
    )
    state = replace(
        state,
        point_match_effects=state.point_match_effects + (effect,),
    )
    return _finish_interactive_effect(
        state, f"-> {source_name}の効果: 相手のポイントをこのカードと同じにする"
    )
