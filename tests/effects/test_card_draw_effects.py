import random

from shadow_bout.engine import (
    resolve_round,
)
from shadow_bout.models import (
    Card,
    Effect,
    EffectType,
    GameState,
    Janken,
    PlayerState,
)


def test_buff_and_peek_adds_point_and_logs_top_card():
    tamaki = Card(
        "card_40",
        "環",
        "たまき",
        Janken.ROCK,
        13,
        Effect(EffectType.BUFF_AND_PEEK, "buff and peek", 2),
    )
    other = Card("cx", "other", "おざー", Janken.ROCK, 13, None)
    top = Card("d1", "でっき1", "でっき1", Janken.PAPER, 1)
    remain = Card("d2", "でっき2", "でっき2", Janken.SCISSORS, 2)
    state = GameState(
        player=PlayerState(hand=[tamaki], deck=[top, remain]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, tamaki, other)

    assert state.player.point_modifier == 2
    assert state.player.deck == [top, remain]
    assert any("山札の一番上はでっき1" in log for log in state.battle_log)


def test_buff_and_peek_adds_point_when_deck_is_empty():
    tamaki = Card(
        "card_40",
        "環",
        "たまき",
        Janken.ROCK,
        13,
        Effect(EffectType.BUFF_AND_PEEK, "buff and peek", 2),
    )
    other = Card("cx", "other", "おざー", Janken.ROCK, 13, None)
    state = GameState(
        player=PlayerState(hand=[tamaki], deck=[]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, tamaki, other)

    assert state.player.point_modifier == 2
    assert any("山札が空のため確認できない" in log for log in state.battle_log)


def test_draw_effect_draws_two_cards_for_both_sides():
    emily = Card(
        "card_20",
        "恵美",
        "めぐみ",
        Janken.ROCK,
        13,
        Effect(EffectType.DRAW, "draw", 2),
    )
    other = Card("cx", "other", "おざー", Janken.ROCK, 13, None)
    p_draw_1 = Card("p1", "p1", "ぴ1", Janken.PAPER, 1)
    p_draw_2 = Card("p2", "p2", "ぴ2", Janken.SCISSORS, 2)
    n_draw_1 = Card("n1", "n1", "ん1", Janken.PAPER, 1)
    n_draw_2 = Card("n2", "n2", "ん2", Janken.SCISSORS, 2)
    state = GameState(
        player=PlayerState(hand=[emily], deck=[p_draw_1, p_draw_2]),
        npc=PlayerState(hand=[other], deck=[n_draw_1, n_draw_2]),
    )

    state = resolve_round(state, emily, other)

    assert state.player.hand == [p_draw_1, p_draw_2]
    assert state.npc.hand == [n_draw_1, n_draw_2]
    assert state.player.deck == []
    assert state.npc.deck == []


def test_draw_effect_handles_partial_draw_when_decks_are_short():
    emily = Card(
        "card_20",
        "恵美",
        "めぐみ",
        Janken.ROCK,
        13,
        Effect(EffectType.DRAW, "draw", 2),
    )
    other = Card("cx", "other", "おざー", Janken.ROCK, 13, None)
    p_draw_only = Card("p1", "p1", "ぴ1", Janken.PAPER, 1)
    state = GameState(
        player=PlayerState(hand=[emily], deck=[p_draw_only]),
        npc=PlayerState(hand=[other], deck=[]),
    )

    state = resolve_round(state, emily, other)

    assert state.player.hand == [p_draw_only]
    assert state.npc.hand == []
    assert state.player.deck == []
    assert state.npc.deck == []


def test_draw_effect_for_haruka_returns_hands_to_deck_then_draws():
    haruka = Card(
        "card_01",
        "春香",
        "はるか",
        Janken.ROCK,
        13,
        Effect(EffectType.DRAW, "draw", 5),
    )
    other = Card("cx", "other", "おざー", Janken.ROCK, 13, None)
    p_hand_1 = Card("p_h1", "p_h1", "ぴ1", Janken.PAPER, 1)
    p_hand_2 = Card("p_h2", "p_h2", "ぴ2", Janken.SCISSORS, 2)
    p_deck_1 = Card("p_d1", "p_d1", "ぴd1", Janken.ROCK, 3)
    p_deck_2 = Card("p_d2", "p_d2", "ぴd2", Janken.ROCK, 4)
    n_hand_1 = Card("n_h1", "n_h1", "ん1", Janken.PAPER, 1)
    n_deck_1 = Card("n_d1", "n_d1", "んd1", Janken.ROCK, 3)
    n_deck_2 = Card("n_d2", "n_d2", "んd2", Janken.ROCK, 4)
    state = GameState(
        player=PlayerState(
            hand=[haruka, p_hand_1, p_hand_2], deck=[p_deck_1, p_deck_2]
        ),
        npc=PlayerState(hand=[other, n_hand_1], deck=[n_deck_1, n_deck_2]),
    )

    state = resolve_round(state, haruka, other)

    assert len(state.player.hand) == 4
    assert len(state.player.deck) == 0
    assert len(state.npc.hand) == 3
    assert len(state.npc.deck) == 0


def test_draw_dynamic_effect_shuffles_discards_into_deck_and_draws_same_count():
    random.seed(0)
    minako = Card(
        "card_19",
        "美奈子",
        "みなこ",
        Janken.SCISSORS,
        11,
        Effect(EffectType.DRAW_DYNAMIC, "draw dynamic", None),
    )
    other = Card("cx", "other", "おざー", Janken.SCISSORS, 11, None)
    p_deck_1 = Card("p_d1", "p_d1", "ぴd1", Janken.ROCK, 3)
    p_discard_1 = Card("p_x1", "p_x1", "ぴx1", Janken.PAPER, 1)
    p_discard_2 = Card("p_x2", "p_x2", "ぴx2", Janken.SCISSORS, 2)
    state = GameState(
        player=PlayerState(
            hand=[minako], deck=[p_deck_1], discard=[p_discard_1, p_discard_2]
        ),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, minako, other)

    assert len(state.player.hand) == 2
    assert len(state.player.deck) == 1
    assert state.player.discard == []


def test_draw_dynamic_effect_noops_when_discard_is_empty():
    minako = Card(
        "card_19",
        "美奈子",
        "みなこ",
        Janken.SCISSORS,
        11,
        Effect(EffectType.DRAW_DYNAMIC, "draw dynamic", None),
    )
    other = Card("cx", "other", "おざー", Janken.SCISSORS, 11, None)
    p_deck_1 = Card("p_d1", "p_d1", "ぴd1", Janken.ROCK, 3)
    state = GameState(
        player=PlayerState(hand=[minako], deck=[p_deck_1], discard=[]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, minako, other)

    assert state.player.hand == []
    assert state.player.deck == [p_deck_1]
    assert state.player.discard == []


def test_draw_dynamic_effect_draws_only_available_cards_when_deck_short():
    random.seed(0)
    minako = Card(
        "card_19",
        "美奈子",
        "みなこ",
        Janken.SCISSORS,
        11,
        Effect(EffectType.DRAW_DYNAMIC, "draw dynamic", None),
    )
    other = Card("cx", "other", "おざー", Janken.SCISSORS, 11, None)
    p_discard_1 = Card("p_x1", "p_x1", "ぴx1", Janken.PAPER, 1)
    p_discard_2 = Card("p_x2", "p_x2", "ぴx2", Janken.SCISSORS, 2)
    p_discard_3 = Card("p_x3", "p_x3", "ぴx3", Janken.ROCK, 3)
    state = GameState(
        player=PlayerState(
            hand=[minako], deck=[], discard=[p_discard_1, p_discard_2, p_discard_3]
        ),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, minako, other)

    assert len(state.player.hand) == 3
    assert state.player.deck == []
    assert state.player.discard == []
