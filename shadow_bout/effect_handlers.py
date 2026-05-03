import random
from dataclasses import replace
from typing import Callable

from shadow_bout.effect_utils import (
    add_banned_card_id,
    clear_forced_card_id,
    get_opponent_side,
    get_player_state,
    set_must_reveal_played_card,
    set_must_reveal_played_card_rounds,
    update_player,
)
from shadow_bout.models import (
    Card,
    GameState,
    Janken,
    PendingEffectContext,
    PersistentPointEffect,
    Phase,
    Side,
)

EffectHandler = Callable[[GameState, Side, Card], GameState]
_registry: dict[str, EffectHandler] = {}


def register(effect_type: str):
    def decorator(fn: EffectHandler):
        _registry[effect_type] = fn
        return fn

    return decorator


def get_effect_handler(effect_type: str) -> EffectHandler | None:
    return _registry.get(effect_type)


def _finish_interactive_effect(state: GameState, log_msg: str) -> GameState:
    return replace(
        state,
        phase=Phase.EFFECT_RESOLUTION,
        pending_effect_context=None,
        battle_log=state.battle_log + [log_msg],
    )


def _find_card(cards: list[Card], card_id: str | None) -> Card | None:
    if card_id is None:
        return None
    return next((card for card in cards if card.id == card_id), None)


def _find_card_by_id(state: GameState, side: Side, card_id: str | None) -> Card | None:
    p_state = get_player_state(state, side)
    card_lists = [
        p_state.hand,
        p_state.deck,
        p_state.discard,
        p_state.won_cards,
        p_state.draw_stock,
    ]
    if state.current_battle is not None:
        card_lists.append(
            [
                state.current_battle.player_card,
                state.current_battle.npc_card,
            ]
        )
    return next(
        (card for cards in card_lists for card in cards if card.id == card_id), None
    )


def _is_immune_active(state: GameState, side: Side) -> bool:
    battle = state.current_battle
    if battle is None:
        return False

    card = battle.player_card if side == Side.PLAYER else battle.npc_card
    return bool(card.effect and card.effect.type.value == "immune")


def _is_blocked_by_immune(
    state: GameState, source_side: Side, target_side: Side
) -> bool:
    if source_side == target_side:
        return False
    return _is_immune_active(state, target_side)


def _parse_card_ids(choice: str | None) -> list[str]:
    if not choice:
        return []
    return [card_id for card_id in choice.split(",") if card_id]


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
        opp_side = get_opponent_side(side)
        if _is_blocked_by_immune(state, side, opp_side):
            return _finish_interactive_effect(
                state, "-> 可憐の効果: 相手のimmuneにより無効"
            )
        state = set_must_reveal_played_card_rounds(state, opp_side, rounds=2)
        return _finish_interactive_effect(
            state, "-> 可憐の効果: 相手は2ラウンドの間、出し札を公開"
        )

    return _finish_interactive_effect(state, "-> 選択効果: 未対応カード")


def _resume_copy_hand(state: GameState, side: Side, choice: str | None) -> GameState:
    p_state = get_player_state(state, side)
    target = _find_card(p_state.hand, choice) or (
        p_state.hand[0] if p_state.hand else None
    )
    if target is None or not target.effect or target.effect.type.value not in _registry:
        return _finish_interactive_effect(state, "-> 杏奈の効果: 発動できる手札なし")

    state = _finish_interactive_effect(
        state, f"-> 杏奈の効果: {target.name}の効果を発動"
    )
    return replace(state, effect_queue=[(side, target)] + state.effect_queue)


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
    p_state = get_player_state(state, side)
    if not p_state.deck:
        return _finish_interactive_effect(state, "-> 茜の効果: 並び替える山札がない")

    selected_ids = _parse_card_ids(choice)
    ordered: list[Card] = []
    used_ids: set[str] = set()
    for card_id in selected_ids:
        card = _find_card(p_state.deck, card_id)
        if card is None or card.id in used_ids:
            continue
        ordered.append(card)
        used_ids.add(card.id)

    ordered.extend(card for card in p_state.deck if card.id not in used_ids)
    state = update_player(state, side, deck=ordered)
    return _finish_interactive_effect(state, "-> 茜の効果: 山札の順番を入れ替えた")


def _resume_removal(state: GameState, side: Side, choice: str | None) -> GameState:
    if choice not in (None, "activate", "yes", "true"):
        return _finish_interactive_effect(state, "-> ジュリアの効果: 発動しない")

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


def resume_pending_effect(state: GameState, choice: str | None = None) -> GameState:
    ctx = state.pending_effect_context
    if not ctx:
        return state

    side = ctx.side
    if ctx.effect == "choose":
        return _resume_choose(state, side, choice)
    if ctx.effect == "copy_hand":
        return _resume_copy_hand(state, side, choice)
    if ctx.effect == "search_and_swap":
        return _resume_search_and_swap(state, side, choice)
    if ctx.effect == "swap":
        return _resume_swap(state, side, choice)
    if ctx.effect == "removal":
        return _resume_removal(state, side, choice)
    if ctx.effect == "salvage":
        return _resume_salvage(state, side, choice)
    if ctx.effect == "reorder":
        return _resume_reorder(state, side, choice)

    return _finish_interactive_effect(state, "-> 選択完了")


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


@register("draw")
def effect_draw(state: GameState, side: Side, card: Card) -> GameState:
    if card.id in ("card_01", "c1"):
        own_state = get_player_state(state, side)
        own_merged_deck = own_state.deck + own_state.hand
        random.shuffle(own_merged_deck)
        own_draw_count = int(card.effect.value or 0)
        own_drawn = own_merged_deck[:own_draw_count]
        state = update_player(
            state,
            side,
            hand=own_drawn,
            deck=own_merged_deck[len(own_drawn) :],
        )

        opp_side = get_opponent_side(side)
        opp_state = get_player_state(state, opp_side)
        opp_merged_deck = opp_state.deck + opp_state.hand
        random.shuffle(opp_merged_deck)
        opp_draw_count = int(card.effect.value or 0)
        opp_drawn = opp_merged_deck[:opp_draw_count]
        state = update_player(
            state,
            opp_side,
            hand=opp_drawn,
            deck=opp_merged_deck[len(opp_drawn) :],
        )

        return replace(
            state,
            battle_log=state.battle_log
            + [
                f"{card.name}の効果発動: お互いの手札を山札に戻して切り、自分は{len(own_drawn)}枚、相手は{len(opp_drawn)}枚ドロー"
            ],
        )

    draw_count = int(card.effect.value or 0)
    own_state = get_player_state(state, side)
    own_drawn = own_state.deck[:draw_count]
    state = update_player(
        state,
        side,
        hand=own_state.hand + own_drawn,
        deck=own_state.deck[len(own_drawn) :],
    )

    opp_side = get_opponent_side(side)
    opp_state = get_player_state(state, opp_side)
    opp_drawn = opp_state.deck[:draw_count]
    state = update_player(
        state,
        opp_side,
        hand=opp_state.hand + opp_drawn,
        deck=opp_state.deck[len(opp_drawn) :],
    )

    return replace(
        state,
        battle_log=state.battle_log
        + [
            f"{card.name}の効果発動: 自分は{len(own_drawn)}枚、相手は{len(opp_drawn)}枚ドロー"
        ],
    )


@register("draw_dynamic")
def effect_draw_dynamic(state: GameState, side: Side, card: Card) -> GameState:
    own_state = get_player_state(state, side)
    moved_count = len(own_state.discard)

    if moved_count == 0:
        return replace(
            state,
            battle_log=state.battle_log + [f"{card.name}の効果発動: 捨札がなく不発"],
        )

    new_deck = own_state.deck + own_state.discard
    random.shuffle(new_deck)
    drawn = new_deck[:moved_count]
    state = update_player(
        state,
        side,
        hand=own_state.hand + drawn,
        deck=new_deck[len(drawn) :],
        discard=[],
    )
    return replace(
        state,
        battle_log=state.battle_log
        + [
            f"{card.name}の効果発動: 捨札{moved_count}枚を山札に戻して{len(drawn)}枚ドロー"
        ],
    )


@register("steal_draw")
def effect_steal_draw(state: GameState, side: Side, card: Card) -> GameState:
    opp_side = get_opponent_side(side)
    opp_state = get_player_state(state, opp_side)

    if not opp_state.deck:
        return replace(
            state,
            battle_log=state.battle_log
            + [f"{card.name}の効果発動: 相手の山札が空のため不発"],
        )

    stolen = opp_state.deck[0]
    state = update_player(
        state,
        opp_side,
        deck=opp_state.deck[1:],
    )

    own_state = get_player_state(state, side)
    state = update_player(
        state,
        side,
        hand=own_state.hand + [stolen],
    )

    return replace(
        state,
        battle_log=state.battle_log
        + [
            f"{card.name}の効果発動: 相手の山札の上から{stolen.name}を奪って手札に加えた"
        ],
    )


@register("steal_hand")
def effect_steal_hand(state: GameState, side: Side, card: Card) -> GameState:
    opp_side = get_opponent_side(side)
    opp_state = get_player_state(state, opp_side)

    if not opp_state.hand:
        return replace(
            state,
            battle_log=state.battle_log
            + [f"{card.name}の効果発動: 相手の手札が空のため不発"],
        )

    stolen_idx = random.randrange(len(opp_state.hand))
    stolen = opp_state.hand[stolen_idx]
    state = update_player(
        state,
        opp_side,
        hand=[c for i, c in enumerate(opp_state.hand) if i != stolen_idx],
    )

    own_state = get_player_state(state, side)
    state = update_player(
        state,
        side,
        hand=own_state.hand + [stolen],
    )

    return replace(
        state,
        battle_log=state.battle_log
        + [f"{card.name}の効果発動: 相手の手札から{stolen.name}を奪って手札に加えた"],
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
    if _is_blocked_by_immune(state, side, opp_side):
        return replace(
            state,
            battle_log=state.battle_log
            + [f"{card.name}の効果発動: 相手のimmuneにより無効"],
        )
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


@register("set_point")
def effect_set_point(state: GameState, side: Side, card: Card) -> GameState:
    opp_side = get_opponent_side(side)
    if _is_blocked_by_immune(state, side, opp_side):
        return replace(
            state,
            battle_log=state.battle_log
            + [f"{card.name}の効果発動: 相手のimmuneにより無効"],
        )
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


@register("conditional_debuff_next")
def effect_conditional_debuff_next(
    state: GameState, side: Side, card: Card
) -> GameState:
    opp_side = get_opponent_side(side)
    if _is_blocked_by_immune(state, side, opp_side):
        return replace(
            state,
            battle_log=state.battle_log
            + [f"{card.name}の効果発動: 相手のimmuneにより無効"],
        )
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


@register("debuff_persistent")
def effect_debuff_persistent(state: GameState, side: Side, card: Card) -> GameState:
    opp_side = get_opponent_side(side)
    if _is_blocked_by_immune(state, side, opp_side):
        return replace(
            state,
            battle_log=state.battle_log
            + [f"{card.name}の効果発動: 相手のimmuneにより無効"],
        )
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
    if _is_blocked_by_immune(state, side, opp_side):
        return replace(
            state,
            battle_log=state.battle_log
            + [f"{card.name}の効果発動: 相手のimmuneにより無効"],
        )
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


@register("negate")
def effect_negate(state: GameState, side: Side, card: Card) -> GameState:
    opp_side = get_opponent_side(side)
    if _is_blocked_by_immune(state, side, opp_side):
        return replace(
            state,
            battle_log=state.battle_log
            + [f"{card.name}の効果発動: 相手のimmuneにより無効"],
        )
    state = update_player(state, opp_side, effect_negated=True)
    return replace(
        state,
        battle_log=state.battle_log
        + [f"{card.name}の効果発動: 相手の戦具効果を無効化"],
    )


@register("force_play")
def effect_force_play(state: GameState, side: Side, card: Card) -> GameState:
    opp_side = get_opponent_side(side)
    if _is_blocked_by_immune(state, side, opp_side):
        return replace(
            state,
            battle_log=state.battle_log
            + [f"{card.name}の効果発動: 相手のimmuneにより無効"],
        )
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
    if _is_blocked_by_immune(state, side, opp_side):
        return replace(
            state,
            battle_log=state.battle_log
            + [f"{card.name}の効果発動: 相手のimmuneにより無効"],
        )
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
    )


@register("choose")
def effect_choose(state: GameState, side: Side, card: Card) -> GameState:
    choose_variant = {
        "card_26": "yuriko_choose",
        "c26": "yuriko_choose",
        "card_45": "karen_choose",
        "c45": "karen_choose",
    }.get(card.id, "generic_choose")
    ctx = PendingEffectContext(
        side=side,
        card_id=card.id,
        effect="choose",
        payload={"choose_variant": choose_variant},
    )
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

    ctx = PendingEffectContext(side=side, card_id=card.id, effect="copy_hand")
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
    if top_card.effect and top_card.effect.type.value in _registry:
        new_queue = [(side, top_card)] + state.effect_queue
        return replace(state, effect_queue=new_queue)

    return state


@register("search_and_swap")
def effect_search_and_swap(state: GameState, side: Side, card: Card) -> GameState:
    ctx = PendingEffectContext(side=side, card_id=card.id, effect="search_and_swap")
    state = replace(
        state, phase=Phase.INTERACTIVE_EFFECT, effect_step=0, pending_effect_context=ctx
    )
    return replace(
        state,
        battle_log=state.battle_log + [f"{card.name}の効果発動: 交換選択待機中..."],
    )


@register("swap")
def effect_swap(state: GameState, side: Side, card: Card) -> GameState:
    ctx = PendingEffectContext(side=side, card_id=card.id, effect="swap")
    state = replace(
        state, phase=Phase.INTERACTIVE_EFFECT, effect_step=0, pending_effect_context=ctx
    )
    return replace(
        state,
        battle_log=state.battle_log + [f"{card.name}の効果発動: 入れ替え選択待機中..."],
    )


@register("removal")
def effect_removal(state: GameState, side: Side, card: Card) -> GameState:
    ctx = PendingEffectContext(side=side, card_id=card.id, effect="removal")
    state = replace(
        state, phase=Phase.INTERACTIVE_EFFECT, effect_step=0, pending_effect_context=ctx
    )
    return replace(
        state, battle_log=state.battle_log + [f"{card.name}の効果発動: 発動待機中..."]
    )


@register("salvage")
def effect_salvage(state: GameState, side: Side, card: Card) -> GameState:
    ctx = PendingEffectContext(side=side, card_id=card.id, effect="salvage")
    state = replace(
        state, phase=Phase.INTERACTIVE_EFFECT, effect_step=0, pending_effect_context=ctx
    )
    return replace(
        state,
        battle_log=state.battle_log + [f"{card.name}の効果発動: 回収選択待機中..."],
    )


@register("reorder")
def effect_reorder(state: GameState, side: Side, card: Card) -> GameState:
    p_state = get_player_state(state, side)
    if len(p_state.deck) <= 1:
        return replace(
            state,
            battle_log=state.battle_log
            + [f"{card.name}の効果発動: 並び替える山札がないため不発"],
        )

    ctx = PendingEffectContext(side=side, card_id=card.id, effect="reorder")
    state = replace(
        state, phase=Phase.INTERACTIVE_EFFECT, effect_step=0, pending_effect_context=ctx
    )
    return replace(
        state,
        battle_log=state.battle_log + [f"{card.name}の効果発動: 並び替え待機中..."],
    )


@register("curse")
def effect_curse(state: GameState, side: Side, card: Card) -> GameState:
    opp_side = get_opponent_side(side)
    state = set_must_reveal_played_card(state, opp_side, True)
    return replace(
        state,
        battle_log=state.battle_log
        + [f"{card.name}の効果発動: 相手の次の出し札を公開"],
    )
