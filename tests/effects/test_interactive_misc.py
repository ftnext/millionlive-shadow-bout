from shadow_bout.engine import (
    process_next_effect,
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
    RoundOutcome,
)


def test_resume_reorder_effect_applies_player_selected_order():
    akane = Card(
        "card_23",
        "茜",
        "あかね",
        Janken.PAPER,
        13,
        Effect(EffectType.REORDER, "reorder", None),
    )
    other = Card("cx", "other", "おざー", Janken.PAPER, 17, None)
    d1 = Card("d1", "draw1", "どろー1", Janken.ROCK, 2)
    d2 = Card("d2", "draw2", "どろー2", Janken.SCISSORS, 3)
    d3 = Card("d3", "draw3", "どろー3", Janken.PAPER, 4)
    state = GameState(
        player=PlayerState(hand=[akane], deck=[d1, d2, d3]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, akane, other)
    assert state.phase == Phase.INTERACTIVE_EFFECT

    state = resume_round_effect(state, choice="d3,d1,d2")

    assert state.phase == Phase.REVEAL
    assert [card.id for card in state.player.deck] == ["d3", "d1", "d2"]


def test_resume_salvage_effect_recovers_from_discard_with_penalty():
    fuka = Card(
        "card_41",
        "風花",
        "ふうか",
        Janken.SCISSORS,
        13,
        Effect(EffectType.SALVAGE, "salvage", -3),
    )
    recovered = Card("cx1", "recover", "りかば", Janken.PAPER, 5, None)
    other = Card("cx2", "other", "おざー", Janken.SCISSORS, 13, None)
    state = GameState(
        player=PlayerState(hand=[fuka], discard=[recovered]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, fuka, other)
    assert state.phase == Phase.INTERACTIVE_EFFECT

    state = resume_round_effect(state, choice="cx1")

    assert state.phase == Phase.REVEAL
    assert state.player.hand == [recovered]
    assert state.player.discard == []
    assert state.current_battle.player_point == 10


def test_resume_salvage_effect_uses_card_defined_penalty_value():
    fuka = Card(
        "card_41",
        "風花",
        "ふうか",
        Janken.SCISSORS,
        13,
        Effect(EffectType.SALVAGE, "salvage", -5),
    )
    recovered = Card("cx1", "recover", "りかば", Janken.PAPER, 5, None)
    other = Card("cx2", "other", "おざー", Janken.SCISSORS, 13, None)
    state = GameState(
        player=PlayerState(hand=[fuka], discard=[recovered]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, fuka, other)
    state = resume_round_effect(state, choice="cx1")

    assert state.current_battle.player_point == 8


def test_resume_salvage_effect_copy_hand_uses_copied_card_penalty_value():
    anna = Card(
        "c4",
        "杏奈",
        "あんな",
        Janken.ROCK,
        14,
        Effect(EffectType.COPY_HAND, "copy_hand", None),
    )
    salvage = Card(
        "c41x",
        "別風花",
        "べつふうか",
        Janken.PAPER,
        10,
        Effect(EffectType.SALVAGE, "salvage", -6),
    )
    recovered = Card("cx1", "recover", "りかば", Janken.PAPER, 5, None)
    other = Card("cx2", "other", "おざー", Janken.ROCK, 14, None)
    state = GameState(
        player=PlayerState(hand=[anna, salvage], discard=[recovered]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, anna, other)
    state = resume_round_effect(state, choice="c41x")
    state = process_next_effect(state)
    state = resume_round_effect(state, choice="cx1")

    assert state.current_battle.player_point == 8


def test_resume_salvage_effect_skip_keeps_state_unchanged():
    fuka = Card(
        "card_41",
        "風花",
        "ふうか",
        Janken.SCISSORS,
        13,
        Effect(EffectType.SALVAGE, "salvage", -3),
    )
    recovered = Card("cx1", "recover", "りかば", Janken.PAPER, 5, None)
    other = Card("cx2", "other", "おざー", Janken.SCISSORS, 13, None)
    state = GameState(
        player=PlayerState(hand=[fuka], discard=[recovered]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, fuka, other)
    assert state.phase == Phase.INTERACTIVE_EFFECT

    state = resume_round_effect(state, choice=None)

    assert state.phase == Phase.REVEAL
    assert state.player.hand == []
    assert state.player.discard == [recovered]
    assert state.current_battle.player_point == 13


def test_resume_salvage_effect_noops_when_discard_is_empty():
    fuka = Card(
        "card_41",
        "風花",
        "ふうか",
        Janken.SCISSORS,
        13,
        Effect(EffectType.SALVAGE, "salvage", -3),
    )
    other = Card("cx2", "other", "おざー", Janken.SCISSORS, 13, None)
    state = GameState(
        player=PlayerState(hand=[fuka], discard=[]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, fuka, other)
    assert state.phase == Phase.INTERACTIVE_EFFECT

    state = resume_round_effect(state, choice="any")

    assert state.phase == Phase.REVEAL
    assert state.player.hand == []
    assert state.player.discard == []
    assert state.current_battle.player_point == 13


def test_resume_removal_effect_skips_winner_and_moves_cards():
    julia = Card(
        "c50",
        "ジュリア",
        "じゅりあ",
        Janken.SCISSORS,
        13,
        Effect(EffectType.REMOVAL, "removal", None),
    )
    other = Card("cx", "other", "おざー", Janken.SCISSORS, 20, None)
    state = GameState(
        player=PlayerState(hand=[julia]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, julia, other)
    assert state.phase == Phase.INTERACTIVE_EFFECT

    state = resume_round_effect(state, choice="activate")

    assert state.phase == Phase.REVEAL
    assert state.removal_activated is True
    assert state.current_battle.outcome == RoundOutcome.EVEN
    assert state.player.deck == [julia]
    assert state.npc.discard == [other]
    assert state.player.won_cards == []
    assert state.npc.won_cards == []
