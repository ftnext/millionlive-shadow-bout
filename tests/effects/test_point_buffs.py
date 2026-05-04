from shadow_bout.engine import (
    proceed_to_next,
    resolve_round,
)
from shadow_bout.models import (
    Card,
    Effect,
    EffectType,
    GameState,
    Janken,
    PlayerState,
    RoundOutcome,
)


def test_mizuki_buff_dynamic_counts_remaining_hand_only():
    mizuki = Card(
        "c44",
        "瑞希",
        "みずき",
        Janken.PAPER,
        17,
        Effect(EffectType.BUFF_DYNAMIC, "hand count", 1),
    )
    extra_1 = Card("e1", "extra1", "え1", Janken.ROCK, 1)
    extra_2 = Card("e2", "extra2", "え2", Janken.SCISSORS, 1)
    other = Card("cx", "other", "おざー", Janken.PAPER, 18, None)
    state = GameState(
        player=PlayerState(hand=[mizuki, extra_1, extra_2]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, mizuki, other)

    assert state.current_battle.player_point == 19
    assert state.current_battle.npc_point == 18
    assert state.current_battle.outcome == RoundOutcome.WIN


def test_buff_next_is_applied_only_on_next_round_for_player_side():
    iori = Card(
        "c7",
        "伊織",
        "いおり",
        Janken.ROCK,
        10,
        Effect(EffectType.BUFF_NEXT, "next +3", 3),
    )
    other = Card("cx", "other", "おざー", Janken.ROCK, 8, None)
    extra_p = Card("p2", "p2", "ぴーつー", Janken.SCISSORS, 5, None)
    extra_n = Card("n2", "n2", "えぬつー", Janken.PAPER, 5, None)
    state = GameState(
        player=PlayerState(hand=[iori, extra_p]),
        npc=PlayerState(hand=[other, extra_n]),
    )

    state = resolve_round(state, iori, other)
    assert state.player.next_round_point_modifier == 3
    assert state.player.point_modifier == 0

    next_state = proceed_to_next(state)
    assert next_state.round_number == 2
    assert next_state.player.point_modifier == 3
    assert next_state.player.next_round_point_modifier == 0

    third_state = proceed_to_next(next_state)
    assert third_state.round_number == 3
    assert third_state.player.point_modifier == 0


def test_buff_snowball_applies_current_and_next_round_when_won():
    konomi = Card(
        "card_39",
        "このみ",
        "このみ",
        Janken.PAPER,
        14,
        Effect(EffectType.BUFF_SNOWBALL, "this +3 and win next +3", 3),
    )
    opponent = Card("n1", "相手", "あいて", Janken.PAPER, 16, None)
    next_player = Card("p2", "p2", "ぴー2", Janken.ROCK, 5, None)
    next_npc = Card("n2", "n2", "えぬ2", Janken.SCISSORS, 5, None)
    state = GameState(
        player=PlayerState(hand=[konomi, next_player]),
        npc=PlayerState(hand=[opponent, next_npc]),
    )

    state = resolve_round(state, konomi, opponent)

    assert state.player.point_modifier == 3
    assert state.current_battle.player_point == 17
    assert state.current_battle.outcome == RoundOutcome.WIN
    assert state.player.next_round_point_modifier == 3

    next_state = proceed_to_next(state)
    assert next_state.round_number == 2
    assert next_state.player.point_modifier == 3
    assert next_state.player.next_round_point_modifier == 0


def test_buff_snowball_applies_current_round_only_when_not_won():
    konomi = Card(
        "card_39",
        "このみ",
        "このみ",
        Janken.PAPER,
        14,
        Effect(EffectType.BUFF_SNOWBALL, "this +3 and win next +3", 3),
    )
    opponent = Card("n1", "相手", "あいて", Janken.PAPER, 18, None)
    next_player = Card("p2", "p2", "ぴー2", Janken.ROCK, 5, None)
    next_npc = Card("n2", "n2", "えぬ2", Janken.SCISSORS, 5, None)
    state = GameState(
        player=PlayerState(hand=[konomi, next_player]),
        npc=PlayerState(hand=[opponent, next_npc]),
    )

    state = resolve_round(state, konomi, opponent)

    assert state.player.point_modifier == 3
    assert state.current_battle.player_point == 17
    assert state.current_battle.outcome == RoundOutcome.LOSE
    assert state.player.next_round_point_modifier == 0

    next_state = proceed_to_next(state)
    assert next_state.round_number == 2
    assert next_state.player.point_modifier == 0


def test_buff_scaling_adds_bonus_by_round_number():
    sayoko = Card(
        "card_27",
        "紗代子",
        "さよこ",
        Janken.PAPER,
        14,
        Effect(EffectType.BUFF_SCALING, "round scaling", None),
    )
    other = Card("cx", "other", "おざー", Janken.PAPER, 14, None)

    for round_number, expected_bonus in ((1, 2), (2, 4), (3, 6), (4, 8)):
        state = GameState(
            player=PlayerState(hand=[sayoko]),
            npc=PlayerState(hand=[other]),
            round_number=round_number,
        )
        state = resolve_round(state, sayoko, other)
        assert state.player.point_modifier == expected_bonus
