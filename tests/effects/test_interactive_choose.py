from shadow_bout.engine import (
    resolve_round,
    resume_round_effect,
)
from shadow_bout.models import (
    Card,
    Effect,
    EffectType,
    GameState,
    Janken,
    Phase,
    PlayerState,
    Side,
)


def test_resume_choose_effect_draw_lets_player_select_returned_cards():
    yuriko = Card(
        "c26",
        "百合子",
        "ゆりこ",
        Janken.PAPER,
        15,
        Effect(EffectType.CHOOSE, "choose", None),
    )
    other = Card("cx", "other", "おざー", Janken.PAPER, 17, None)
    hand_card = Card("h1", "hand", "はんど", Janken.ROCK, 1)
    draw_1 = Card("d1", "draw1", "どろー1", Janken.ROCK, 2)
    draw_2 = Card("d2", "draw2", "どろー2", Janken.SCISSORS, 3)
    state = GameState(
        player=PlayerState(hand=[yuriko, hand_card], deck=[draw_1, draw_2]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, yuriko, other)
    state = resume_round_effect(state, choice="draw_cards")

    assert state.phase == Phase.INTERACTIVE_EFFECT
    assert state.pending_effect_context.side == Side.PLAYER
    assert state.pending_effect_context.step == 1
    assert state.player.hand == [hand_card, draw_1, draw_2]

    state = resume_round_effect(state, choice="h1,d2")

    assert state.phase == Phase.REVEAL
    assert state.player.hand == [draw_1]


def test_umi_choose_multiple_discard_only_applies_buff():
    umi = Card(
        "card_29",
        "海美",
        "うみ",
        Janken.SCISSORS,
        14,
        Effect(EffectType.CHOOSE_MULTIPLE, "choose_multiple", None),
    )
    hand_card = Card("h1", "手札", "てふだ", Janken.ROCK, 5)
    other = Card("cx", "other", "おざー", Janken.SCISSORS, 14, None)
    state = GameState(
        player=PlayerState(hand=[umi, hand_card]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, umi, other)
    state = resume_round_effect(state, choice="discard_buff")

    assert state.player.point_modifier == 5
    assert state.player.hand == []
    assert state.player.discard == [hand_card, umi]


def test_umi_choose_multiple_draw_only_applies_debuff():
    umi = Card(
        "card_29",
        "海美",
        "うみ",
        Janken.SCISSORS,
        14,
        Effect(EffectType.CHOOSE_MULTIPLE, "choose_multiple", None),
    )
    draw_card = Card("d1", "山札", "やまふだ", Janken.PAPER, 6)
    other = Card("cx", "other", "おざー", Janken.SCISSORS, 14, None)
    state = GameState(
        player=PlayerState(hand=[umi], deck=[draw_card]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, umi, other)
    state = resume_round_effect(state, choice="draw_debuff")

    assert state.player.point_modifier == -2
    assert state.player.hand == [draw_card]
    assert state.player.deck == []


def test_umi_choose_multiple_both_applies_sum_without_order_dependency():
    umi = Card(
        "card_29",
        "海美",
        "うみ",
        Janken.SCISSORS,
        14,
        Effect(EffectType.CHOOSE_MULTIPLE, "choose_multiple", None),
    )
    hand_card = Card("h1", "手札", "てふだ", Janken.ROCK, 5)
    draw_card = Card("d1", "山札", "やまふだ", Janken.PAPER, 6)
    other = Card("cx", "other", "おざー", Janken.SCISSORS, 14, None)
    state = GameState(
        player=PlayerState(hand=[umi, hand_card], deck=[draw_card]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, umi, other)
    state = resume_round_effect(state, choice="draw_debuff,discard_buff")

    assert state.player.point_modifier == 3
    assert state.player.hand == [draw_card]
    assert state.player.deck == []
    assert state.player.discard == [hand_card, umi]


def test_umi_choose_multiple_no_available_option_is_safe():
    umi = Card(
        "card_29",
        "海美",
        "うみ",
        Janken.SCISSORS,
        14,
        Effect(EffectType.CHOOSE_MULTIPLE, "choose_multiple", None),
    )
    other = Card("cx", "other", "おざー", Janken.SCISSORS, 14, None)
    state = GameState(
        player=PlayerState(hand=[umi]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, umi, other)

    assert state.phase == Phase.REVEAL
    assert state.pending_effect_context is None
    assert state.player.point_modifier == 0


def test_umi_choose_multiple_none_choice_keeps_interactive():
    umi = Card(
        "card_29",
        "海美",
        "うみ",
        Janken.SCISSORS,
        14,
        Effect(EffectType.CHOOSE_MULTIPLE, "choose_multiple", None),
    )
    hand_card = Card("h1", "手札", "てふだ", Janken.ROCK, 5)
    other = Card("cx", "other", "おざー", Janken.SCISSORS, 14, None)
    state = GameState(
        player=PlayerState(hand=[umi, hand_card]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, umi, other)
    state = resume_round_effect(state, choice=None)

    assert state.phase == Phase.INTERACTIVE_EFFECT
    assert state.pending_effect_context is not None
    assert state.pending_effect_context.effect == "choose_multiple"
    assert state.player.point_modifier == 0


def test_umi_choose_multiple_empty_choice_keeps_interactive():
    umi = Card(
        "card_29",
        "海美",
        "うみ",
        Janken.SCISSORS,
        14,
        Effect(EffectType.CHOOSE_MULTIPLE, "choose_multiple", None),
    )
    hand_card = Card("h1", "手札", "てふだ", Janken.ROCK, 5)
    other = Card("cx", "other", "おざー", Janken.SCISSORS, 14, None)
    state = GameState(
        player=PlayerState(hand=[umi, hand_card]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, umi, other)
    state = resume_round_effect(state, choice="")

    assert state.phase == Phase.INTERACTIVE_EFFECT
    assert state.pending_effect_context is not None
    assert state.pending_effect_context.effect == "choose_multiple"
    assert state.player.point_modifier == 0
