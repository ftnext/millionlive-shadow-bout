import random

from shadow_bout.effects import calculate_effective_point
from shadow_bout.engine import (
    proceed_to_next,
    resolve_npc_pending_effects,
    resolve_round,
    resume_round_effect,
)
from shadow_bout.models import (
    Card,
    Effect,
    EffectType,
    GameState,
    Janken,
    JankenResult,
    Phase,
    PlayerState,
    RoundOutcome,
)
from tests.effects.helpers import FirstChoiceStrategy


def _karen() -> Card:
    return Card(
        "card_45",
        "可憐",
        "かれん",
        Janken.SCISSORS,
        11,
        Effect(EffectType.CHOOSE, "choose", None),
    )


def test_karen_choose_gain_points_increments_point_modifier():
    karen = _karen()
    other = Card("cx", "other", "おざー", Janken.SCISSORS, 11, None)
    state = GameState(
        player=PlayerState(hand=[karen]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, karen, other)
    assert state.phase == Phase.INTERACTIVE_EFFECT

    state = resume_round_effect(state, choice="gain_points")

    assert state.player.point_modifier == 2


def test_karen_choose_return_and_flip_replaces_played_card_without_triggering_new_effect(
    monkeypatch,
):
    karen = _karen()
    other = Card("cx", "other", "おざー", Janken.SCISSORS, 11, None)
    deck_card = Card(
        "d1",
        "山札",
        "やまふだ",
        Janken.SCISSORS,
        20,
        Effect(EffectType.BUFF, "+5", 5),
    )
    state = GameState(
        player=PlayerState(hand=[karen], deck=[deck_card]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, karen, other)
    assert state.phase == Phase.INTERACTIVE_EFFECT

    monkeypatch.setattr(random, "shuffle", lambda _seq: None)
    state = resume_round_effect(state, choice="return_and_flip")

    assert state.current_battle.player_card.id == deck_card.id
    assert state.player.point_modifier == 0
    assert [c.id for c in state.player.deck] == [karen.id]


def test_karen_choose_return_and_flip_with_empty_deck_keeps_karen_on_field():
    karen = _karen()
    other = Card("cx", "other", "おざー", Janken.SCISSORS, 11, None)
    state = GameState(
        player=PlayerState(hand=[karen], deck=[]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, karen, other)
    assert state.phase == Phase.INTERACTIVE_EFFECT

    state = resume_round_effect(state, choice="return_and_flip")

    assert state.current_battle.player_card.id == karen.id
    assert state.player.deck == []
    assert any("再び可憐がめくれた" in log for log in state.battle_log)


def test_karen_choose_npc_side_uses_strategy_to_select_gain_points():
    karen = _karen()
    player_card = Card("cx", "other", "おざー", Janken.SCISSORS, 11, None)
    state = GameState(
        player=PlayerState(hand=[player_card]),
        npc=PlayerState(hand=[karen]),
    )

    state = resolve_round(state, player_card, karen)
    assert state.phase == Phase.INTERACTIVE_EFFECT

    state = resolve_npc_pending_effects(state, FirstChoiceStrategy())

    assert state.npc.point_modifier == 2


def test_change_janken_arisa_rejudges_current_battle_mark():
    arisa = Card(
        "card_28",
        "亜利沙",
        "ありさ",
        Janken.ROCK,
        11,
        Effect(
            EffectType.CHANGE_JANKEN, "change current field to scissors", "scissors"
        ),
    )
    opponent = Card("op", "相手", "あいて", Janken.ROCK, 30, None)
    state = GameState(
        player=PlayerState(hand=[arisa]),
        npc=PlayerState(hand=[opponent]),
    )

    state = resolve_round(state, arisa, opponent)

    assert state.phase == Phase.REVEAL
    assert state.current_battle.janken_result == JankenResult.WIN
    assert state.current_battle.outcome == RoundOutcome.WIN
    assert state.current_battle.player_point is None
    assert state.current_battle.npc_point is None
    assert state.player.won_cards == [opponent]
    assert any("効果解決後じゃんけん再判定" in log for log in state.battle_log)


def test_change_janken_ritsuko_applies_rock_override_only_next_round():
    ritsuko = Card(
        "card_09",
        "律子",
        "りつこ",
        Janken.PAPER,
        16,
        Effect(EffectType.CHANGE_JANKEN, "next opponent marks to rock", "rock"),
    )
    first_opponent = Card("n1", "相手1", "あいて1", Janken.PAPER, 10, None)
    player_next = Card("p2", "次自分", "つぎじぶん", Janken.SCISSORS, 5, None)
    npc_next = Card("n2", "次相手", "つぎあいて", Janken.PAPER, 5, None)
    state = GameState(
        player=PlayerState(hand=[ritsuko, player_next]),
        npc=PlayerState(hand=[first_opponent, npc_next]),
    )

    state = resolve_round(state, ritsuko, first_opponent)
    assert state.current_battle.outcome == RoundOutcome.WIN
    assert state.npc.next_round_janken_override == Janken.ROCK

    next_state = proceed_to_next(state)
    assert next_state.round_number == 2
    assert next_state.npc.janken_override == Janken.ROCK
    assert next_state.npc.next_round_janken_override is None

    next_state = resolve_round(next_state, player_next, npc_next)

    assert next_state.current_battle.janken_result == JankenResult.LOSE
    assert next_state.current_battle.outcome == RoundOutcome.LOSE

    third_state = proceed_to_next(next_state)
    assert third_state.npc.janken_override is None


def test_conditional_debuff_next_is_applied_only_on_next_round_for_npc_side():
    subaru = Card(
        "c47",
        "昴",
        "すばる",
        Janken.PAPER,
        12,
        Effect(EffectType.CONDITIONAL_DEBUFF_NEXT, "next -3", -3),
    )
    other = Card("cx", "other", "おざー", Janken.PAPER, 12, None)
    extra_p = Card("p2", "p2", "ぴーつー", Janken.SCISSORS, 5, None)
    extra_n = Card("n2", "n2", "えぬつー", Janken.ROCK, 5, None)
    state = GameState(
        player=PlayerState(hand=[other, extra_p]),
        npc=PlayerState(hand=[subaru, extra_n]),
    )

    state = resolve_round(state, other, subaru)
    assert state.player.next_round_conditional_point_modifier_non_wildcard == -3
    assert state.player.point_modifier == 0

    next_state = proceed_to_next(state)
    assert next_state.round_number == 2
    assert next_state.player.conditional_point_modifier_non_wildcard == -3
    assert next_state.player.next_round_conditional_point_modifier_non_wildcard == 0

    third_state = proceed_to_next(next_state)
    assert third_state.round_number == 3
    assert third_state.player.point_modifier == 0


def test_conditional_debuff_next_does_not_apply_to_wildcard():
    subaru = Card(
        "c47",
        "昴",
        "すばる",
        Janken.PAPER,
        12,
        Effect(EffectType.CONDITIONAL_DEBUFF_NEXT, "next -3", -3),
    )
    wildcard = Card("cw", "バー", "ばー", Janken.WILDCARD, 10, None)
    player_card = Card("pr", "pr", "ぴーあーる", Janken.PAPER, 10, None)
    npc_other = Card("n2", "n2", "えぬつー", Janken.ROCK, 5, None)
    player_other = Card("p2", "p2", "ぴーつー", Janken.SCISSORS, 5, None)
    state = GameState(
        player=PlayerState(hand=[player_card, wildcard, player_other]),
        npc=PlayerState(hand=[subaru, npc_other]),
    )

    state = resolve_round(state, player_card, subaru)
    next_state = proceed_to_next(state)

    assert next_state.player.conditional_point_modifier_non_wildcard == -3
    assert next_state.player.point_modifier == 0
    assert calculate_effective_point(wildcard, next_state.player) == wildcard.base_point


def test_conditional_buff_applies_when_opponent_won_total_is_higher():
    noriko = Card(
        "card_43",
        "のり子",
        "のりこ",
        Janken.PAPER,
        14,
        Effect(EffectType.CONDITIONAL_BUFF, "conditional buff", 7),
    )
    other = Card("cx", "other", "おざー", Janken.PAPER, 14, None)
    own_won = Card("w1", "own", "おうん", Janken.ROCK, 10)
    opp_won = Card("w2", "opp", "おっぷ", Janken.ROCK, 16)
    state = GameState(
        player=PlayerState(hand=[noriko], won_cards=[own_won]),
        npc=PlayerState(hand=[other], won_cards=[opp_won]),
    )

    state = resolve_round(state, noriko, other)

    assert state.phase == Phase.REVEAL
    assert state.current_battle.player_point == 21
    assert state.current_battle.npc_point == 14
    assert any("ポイント+7" in log for log in state.battle_log)


def test_conditional_buff_does_not_apply_when_opponent_won_total_is_not_higher():
    noriko = Card(
        "card_43",
        "のり子",
        "のりこ",
        Janken.PAPER,
        14,
        Effect(EffectType.CONDITIONAL_BUFF, "conditional buff", 7),
    )
    other = Card("cx", "other", "おざー", Janken.PAPER, 14, None)
    own_won = Card("w1", "own", "おうん", Janken.ROCK, 16)
    opp_won = Card("w2", "opp", "おっぷ", Janken.ROCK, 10)
    state = GameState(
        player=PlayerState(hand=[noriko], won_cards=[own_won]),
        npc=PlayerState(hand=[other], won_cards=[opp_won]),
    )

    state = resolve_round(state, noriko, other)

    assert state.phase == Phase.REVEAL
    assert state.current_battle.player_point == 14
    assert state.current_battle.npc_point == 14
    assert any("不発" in log for log in state.battle_log)


def test_conditional_negate_buff_applies_when_opponent_point_is_odd():
    nao = Card(
        "card_37",
        "奈緒",
        "なお",
        Janken.PAPER,
        12,
        Effect(EffectType.CONDITIONAL_NEGATE_BUFF, "conditional negate buff", 3),
    )
    other = Card(
        "cx",
        "other",
        "おざー",
        Janken.PAPER,
        13,
        Effect(EffectType.BUFF, "+5", 5),
    )
    state = GameState(player=PlayerState(hand=[nao]), npc=PlayerState(hand=[other]))

    state = resolve_round(state, nao, other)

    assert state.phase == Phase.REVEAL
    assert state.player.point_modifier == 3
    assert state.npc.effect_negated is True
    assert state.current_battle.player_point == 15
    assert state.current_battle.npc_point == 13
    assert any("相手のポイント(13)が奇数" in log for log in state.battle_log)


def test_conditional_negate_buff_does_not_apply_when_opponent_point_is_even():
    nao = Card(
        "card_37",
        "奈緒",
        "なお",
        Janken.PAPER,
        12,
        Effect(EffectType.CONDITIONAL_NEGATE_BUFF, "conditional negate buff", 3),
    )
    other = Card(
        "cx",
        "other",
        "おざー",
        Janken.PAPER,
        14,
        Effect(EffectType.BUFF, "+5", 5),
    )
    state = GameState(player=PlayerState(hand=[nao]), npc=PlayerState(hand=[other]))

    state = resolve_round(state, nao, other)

    assert state.phase == Phase.REVEAL
    assert state.player.point_modifier == 0
    assert state.npc.effect_negated is False
    assert state.current_battle.player_point == 12
    assert state.current_battle.npc_point == 19
    assert any("相手のポイント(14)が偶数のため不発" in log for log in state.battle_log)


def test_conditional_negate_buff_keeps_own_buff_against_immune_opponent():
    nao = Card(
        "card_37",
        "奈緒",
        "なお",
        Janken.PAPER,
        12,
        Effect(EffectType.CONDITIONAL_NEGATE_BUFF, "conditional negate buff", 3),
    )
    emily = Card(
        "card_32",
        "エミリー",
        "えみりー",
        Janken.PAPER,
        13,
        Effect(EffectType.IMMUNE, "immune", None),
    )
    state = GameState(player=PlayerState(hand=[nao]), npc=PlayerState(hand=[emily]))

    state = resolve_round(state, nao, emily)

    assert state.phase == Phase.REVEAL
    assert state.player.point_modifier == 3
    assert state.npc.effect_negated is False
    assert state.current_battle.player_point == 15
    assert state.current_battle.npc_point == 13
    assert any("戦具効果を受けないため無効化できず" in log for log in state.battle_log)
