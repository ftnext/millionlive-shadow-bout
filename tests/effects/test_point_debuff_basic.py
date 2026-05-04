from shadow_bout.engine import (
    proceed_to_next,
    resolve_round,
    resume_round_effect,
)
from shadow_bout.models import (
    Card,
    Effect,
    EffectType,
    GameState,
    Janken,
    PersistentPointEffect,
    Phase,
    PlayerState,
    RoundOutcome,
    Side,
)


def test_debuff_yukiho_halves_opponent_point_floor_for_even_and_odd():
    yukiho = Card(
        "card_04",
        "雪歩",
        "ゆきほ",
        Janken.PAPER,
        11,
        Effect(EffectType.DEBUFF, "halve opponent point", 0.5),
    )
    odd_point_card = Card("p_odd", "p_odd", "ぴーodd", Janken.PAPER, 11, None)
    even_point_card = Card("p_even", "p_even", "ぴーeven", Janken.PAPER, 12, None)
    n_other = Card("n2", "n2", "えぬ2", Janken.PAPER, 1, None)

    odd_state = GameState(
        player=PlayerState(hand=[odd_point_card]),
        npc=PlayerState(hand=[yukiho, n_other]),
    )
    odd_state = resolve_round(odd_state, odd_point_card, yukiho)
    assert odd_state.current_battle.player_point == 5

    even_state = GameState(
        player=PlayerState(hand=[even_point_card]),
        npc=PlayerState(hand=[yukiho, n_other]),
    )
    even_state = resolve_round(even_state, even_point_card, yukiho)
    assert even_state.current_battle.player_point == 6


def test_debuff_kotoha_reduces_by_opponent_hand_count():
    kotoha = Card(
        "card_17",
        "琴葉",
        "ことは",
        Janken.SCISSORS,
        14,
        Effect(EffectType.DEBUFF, "opponent hand count x -1", -1),
    )
    p_card = Card("p1", "p1", "ぴー1", Janken.SCISSORS, 15, None)
    p_extra_1 = Card("p2", "p2", "ぴー2", Janken.ROCK, 1, None)
    p_extra_2 = Card("p3", "p3", "ぴー3", Janken.PAPER, 1, None)
    n_other = Card("n2", "n2", "えぬ2", Janken.SCISSORS, 1, None)
    state = GameState(
        player=PlayerState(hand=[p_card, p_extra_1, p_extra_2]),
        npc=PlayerState(hand=[kotoha, n_other]),
    )

    state = resolve_round(state, p_card, kotoha)

    assert state.current_battle.player_point == 13


def test_debuff_counterable_applies_debuff_when_opponent_skips_counter():
    shiho = Card(
        "card_33",
        "志保",
        "しほ",
        Janken.ROCK,
        11,
        Effect(EffectType.DEBUFF_COUNTERABLE, "counterable -5", -5),
    )
    opponent = Card("op", "opponent", "おざー", Janken.ROCK, 14, None)
    extra = Card("n_extra", "n_extra", "ん", Janken.PAPER, 1, None)
    state = GameState(
        player=PlayerState(hand=[shiho]),
        npc=PlayerState(hand=[opponent, extra]),
    )

    state = resolve_round(state, shiho, opponent)
    assert state.phase == Phase.INTERACTIVE_EFFECT
    assert state.pending_effect_context.side == Side.NPC

    state = resume_round_effect(state, choice="skip")

    assert state.phase == Phase.REVEAL
    assert state.current_battle.player_point == 11
    assert state.current_battle.npc_point == 9
    assert state.current_battle.outcome == RoundOutcome.WIN
    assert state.npc.hand == [extra]


def test_debuff_counterable_discards_one_hand_card_and_negates_debuff():
    shiho = Card(
        "card_33",
        "志保",
        "しほ",
        Janken.ROCK,
        11,
        Effect(EffectType.DEBUFF_COUNTERABLE, "counterable -5", -5),
    )
    opponent = Card("op", "opponent", "おざー", Janken.ROCK, 14, None)
    extra = Card("n_extra", "n_extra", "ん", Janken.PAPER, 1, None)
    state = GameState(
        player=PlayerState(hand=[shiho]),
        npc=PlayerState(hand=[opponent, extra]),
    )

    state = resolve_round(state, shiho, opponent)
    state = resume_round_effect(state, choice=extra.id)

    assert state.phase == Phase.REVEAL
    assert state.current_battle.player_point == 11
    assert state.current_battle.npc_point == 14
    assert state.current_battle.outcome == RoundOutcome.LOSE
    assert state.npc.hand == []
    assert state.npc.discard == [extra, opponent]


def test_debuff_counterable_applies_debuff_when_opponent_has_no_hand():
    shiho = Card(
        "card_33",
        "志保",
        "しほ",
        Janken.ROCK,
        11,
        Effect(EffectType.DEBUFF_COUNTERABLE, "counterable -5", -5),
    )
    opponent = Card("op", "opponent", "おざー", Janken.ROCK, 14, None)
    state = GameState(
        player=PlayerState(hand=[shiho]),
        npc=PlayerState(hand=[opponent]),
    )

    state = resolve_round(state, shiho, opponent)

    assert state.phase == Phase.REVEAL
    assert state.pending_effect_context is None
    assert state.current_battle.player_point == 11
    assert state.current_battle.npc_point == 9
    assert state.current_battle.outcome == RoundOutcome.WIN


def test_set_point_azusa_sets_opponent_point_to_zero():
    azusa = Card(
        "card_10",
        "あずさ",
        "あずさ",
        Janken.SCISSORS,
        10,
        Effect(EffectType.SET_POINT, "set point", 0),
    )
    other = Card("op", "other", "おざー", Janken.SCISSORS, 18, None)
    state = GameState(
        player=PlayerState(hand=[azusa]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, azusa, other)

    assert state.current_battle.player_point == 10
    assert state.current_battle.npc_point == 0
    assert state.current_battle.outcome == RoundOutcome.WIN


def test_set_point_works_consistently_with_existing_point_modifier_order():
    azusa = Card(
        "card_10",
        "あずさ",
        "あずさ",
        Janken.SCISSORS,
        10,
        Effect(EffectType.SET_POINT, "set point", 0),
    )
    takane = Card(
        "c8",
        "貴音",
        "たかね",
        Janken.SCISSORS,
        14,
        Effect(EffectType.BUFF, "+1", 1),
    )
    state = GameState(
        player=PlayerState(hand=[azusa]),
        npc=PlayerState(hand=[takane]),
    )

    state = resolve_round(state, azusa, takane)

    assert state.current_battle.player_point == 10
    # あずさ(10)→貴音(14)の順で効果解決されるため、0固定の後に+1される
    assert state.current_battle.npc_point == 1
    assert state.current_battle.outcome == RoundOutcome.WIN


def test_set_point_match_ayumu_matches_opponent_final_point_when_activated():
    ayumu = Card(
        "card_34",
        "歩",
        "あゆむ",
        Janken.ROCK,
        12,
        Effect(EffectType.SET_POINT_MATCH, "set point match", None),
    )
    opponent = Card("op", "opponent", "おざー", Janken.ROCK, 18, None)
    state = GameState(
        player=PlayerState(hand=[ayumu]),
        npc=PlayerState(hand=[opponent]),
    )

    state = resolve_round(state, ayumu, opponent)
    assert state.phase == Phase.INTERACTIVE_EFFECT

    state = resume_round_effect(state, choice="activate")

    assert state.current_battle.player_point == 12
    assert state.current_battle.npc_point == 12
    assert state.current_battle.outcome == RoundOutcome.EVEN


def test_set_point_match_ayumu_can_be_skipped():
    ayumu = Card(
        "card_34",
        "歩",
        "あゆむ",
        Janken.ROCK,
        12,
        Effect(EffectType.SET_POINT_MATCH, "set point match", None),
    )
    opponent = Card("op", "opponent", "おざー", Janken.ROCK, 18, None)
    state = GameState(
        player=PlayerState(hand=[ayumu]),
        npc=PlayerState(hand=[opponent]),
    )

    state = resolve_round(state, ayumu, opponent)
    state = resume_round_effect(state, choice="skip")

    assert state.current_battle.player_point == 12
    assert state.current_battle.npc_point == 18
    assert state.current_battle.outcome == RoundOutcome.LOSE


def test_set_point_match_ayumu_matches_after_later_point_modifier():
    ayumu = Card(
        "card_34",
        "歩",
        "あゆむ",
        Janken.ROCK,
        12,
        Effect(EffectType.SET_POINT_MATCH, "set point match", None),
    )
    takane = Card(
        "c8",
        "貴音",
        "たかね",
        Janken.ROCK,
        14,
        Effect(EffectType.BUFF, "+1", 1),
    )
    state = GameState(
        player=PlayerState(hand=[ayumu]),
        npc=PlayerState(hand=[takane]),
    )

    state = resolve_round(state, ayumu, takane)
    state = resume_round_effect(state, choice="activate")

    assert state.current_battle.player_point == 12
    assert state.current_battle.npc_point == 12
    assert state.current_battle.outcome == RoundOutcome.EVEN


def test_debuff_persistent_applies_current_and_next_round_only():
    hinata = Card(
        "c35",
        "ひなた",
        "ひなた",
        Janken.ROCK,
        10,
        Effect(EffectType.DEBUFF_PERSISTENT, "this and next -2", -2),
    )
    player_card = Card("p1", "p1", "ぴー1", Janken.ROCK, 10, None)
    p_next = Card("p2", "p2", "ぴー2", Janken.PAPER, 10, None)
    n_next = Card("n2", "n2", "えぬ2", Janken.SCISSORS, 10, None)
    state = GameState(
        player=PlayerState(hand=[player_card, p_next]),
        npc=PlayerState(hand=[hinata, n_next]),
    )

    state = resolve_round(state, player_card, hinata)
    assert state.player.point_modifier == -2
    assert state.player.persistent_point_effects == (
        PersistentPointEffect(value=-2, remaining_turns=1),
    )

    next_state = proceed_to_next(state)
    assert next_state.round_number == 2
    assert next_state.player.point_modifier == -2
    assert next_state.player.persistent_point_effects == ()

    third_state = proceed_to_next(next_state)
    assert third_state.round_number == 3
    assert third_state.player.point_modifier == 0


def test_debuff_conditional_elena_applies_only_when_lost():
    elena = Card(
        "card_18",
        "エレナ",
        "えれな",
        Janken.ROCK,
        12,
        Effect(EffectType.DEBUFF_CONDITIONAL, "lose then next -3", -3),
    )
    lose_state = GameState(
        player=PlayerState(hand=[elena]),
        npc=PlayerState(
            hand=[Card("n_lose", "n_lose", "えぬlose", Janken.ROCK, 13, None)]
        ),
    )
    lose_state = resolve_round(lose_state, elena, lose_state.npc.hand[0])
    assert lose_state.npc.next_round_conditional_point_modifier_non_wildcard == -3

    not_lose_state = GameState(
        player=PlayerState(hand=[elena]),
        npc=PlayerState(
            hand=[Card("n_win", "n_win", "えぬwin", Janken.ROCK, 10, None)]
        ),
    )
    not_lose_state = resolve_round(not_lose_state, elena, not_lose_state.npc.hand[0])
    assert not_lose_state.npc.next_round_conditional_point_modifier_non_wildcard == 0


def test_debuff_conditional_elena_does_not_apply_when_negated():
    elena = Card(
        "card_18",
        "エレナ",
        "えれな",
        Janken.ROCK,
        12,
        Effect(EffectType.DEBUFF_CONDITIONAL, "lose then next -3", -3),
    )
    chihaya = Card(
        "c2",
        "千早",
        "ちはや",
        Janken.ROCK,
        11,
        Effect(EffectType.NEGATE, "negate", None),
    )
    state = GameState(
        player=PlayerState(hand=[elena]),
        npc=PlayerState(hand=[chihaya], point_modifier=2),
    )

    state = resolve_round(state, elena, chihaya)

    assert state.current_battle.outcome == RoundOutcome.LOSE
    assert state.npc.next_round_conditional_point_modifier_non_wildcard == 0


def test_debuff_conditional_iku_applies_from_round_3():
    iku = Card(
        "card_30",
        "育",
        "いく",
        Janken.ROCK,
        12,
        Effect(EffectType.DEBUFF_CONDITIONAL, "round 3+ next -4", -4),
    )
    player_card = Card("p1", "p1", "ぴー1", Janken.ROCK, 12, None)
    n_other = Card("n2", "n2", "えぬ2", Janken.ROCK, 10, None)

    for round_number in (1, 2):
        state = GameState(
            player=PlayerState(hand=[player_card]),
            npc=PlayerState(hand=[iku, n_other]),
            round_number=round_number,
        )
        state = resolve_round(state, player_card, iku)
        assert state.player.next_round_conditional_point_modifier_non_wildcard == 0

    for round_number in (3, 4):
        state = GameState(
            player=PlayerState(hand=[player_card]),
            npc=PlayerState(hand=[iku, n_other]),
            round_number=round_number,
        )
        state = resolve_round(state, player_card, iku)
        assert state.player.next_round_conditional_point_modifier_non_wildcard == -4
