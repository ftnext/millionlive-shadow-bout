import random

from shadow_bout.effects import calculate_effective_point
from shadow_bout.engine import (
    continue_round_effect_step,
    resolve_npc_pending_effects,
    resolve_round,
    resolve_round_stepwise,
    resume_round_effect,
    resume_round_effect_stepwise,
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
    Side,
)
from tests.effects.helpers import FirstChoiceStrategy


def test_basic_point_calculation():
    # 1. 基本ポイント計算
    c = Card("c1", "test", "test", Janken.ROCK, 15)
    p = PlayerState(hand=[c, c, c])  # 3 cards
    assert calculate_effective_point(c, p) == 15


def test_chihaya_vs_yayoi():
    # 2. 千早 vs やよい
    yayoi = Card(
        "c5", "やよい", "やよい", Janken.PAPER, 15, Effect(EffectType.BUFF, "+5", 5)
    )
    chihaya = Card(
        "c2",
        "千早",
        "ちはや",
        Janken.ROCK,
        13,
        Effect(EffectType.NEGATE, "negate", None),
    )

    # engine resolve_round should result in negate being processed first (13 < 15)
    state = GameState(
        player=PlayerState(hand=[yayoi]),
        npc=PlayerState(hand=[chihaya]),
    )
    # ROCK vs PAPER -> player (PAPER) wins. Wait, we need DRAW to test effects.
    # Let's change janken for test
    yayoi_rock = Card(
        "c5", "やよい", "やよい", Janken.ROCK, 15, Effect(EffectType.BUFF, "+5", 5)
    )
    state = resolve_round(state, yayoi_rock, chihaya)

    assert state.phase == Phase.REVEAL
    # Yayoi should be negated. Her point modifier should be 0.
    # Chihaya points: 13 + 1 = 14
    # Yayoi points: 15 + 1 = 16 (negated, so +5 not applied)
    # 16 > 14, Yayoi wins.
    assert state.current_battle.outcome == RoundOutcome.WIN


def test_stepwise_effect_resolution_waits_between_weapon_effects():
    yayoi = Card(
        "c5", "やよい", "やよい", Janken.ROCK, 15, Effect(EffectType.BUFF, "+5", 5)
    )
    takane = Card(
        "c8", "貴音", "たかね", Janken.ROCK, 14, Effect(EffectType.BUFF, "+1", 1)
    )
    state = GameState(
        player=PlayerState(hand=[yayoi]),
        npc=PlayerState(hand=[takane]),
    )

    state = resolve_round_stepwise(state, yayoi, takane)

    assert state.phase == Phase.EFFECT_RESOLUTION
    assert state.effect_queue == [(Side.NPC, takane), (Side.PLAYER, yayoi)]

    state = continue_round_effect_step(state)

    assert state.phase == Phase.EFFECT_RESOLUTION
    assert state.effect_queue == [(Side.PLAYER, yayoi)]
    assert state.npc.point_modifier == 1

    state = continue_round_effect_step(state)

    assert state.phase == Phase.REVEAL
    assert state.current_battle.player_point == 20
    assert state.current_battle.npc_point == 15
    assert state.current_battle.outcome == RoundOutcome.WIN


def test_resume_choose_effect_finalizes_round_with_buff():
    yuriko = Card(
        "c26",
        "百合子",
        "ゆりこ",
        Janken.PAPER,
        15,
        Effect(EffectType.CHOOSE, "choose", None),
    )
    other = Card("cx", "other", "おざー", Janken.PAPER, 17, None)
    state = GameState(
        player=PlayerState(hand=[yuriko]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, yuriko, other)
    assert state.phase == Phase.INTERACTIVE_EFFECT

    state = resume_round_effect(state, choice="gain_points")

    assert state.phase == Phase.REVEAL
    assert state.current_battle.player_point == 18
    assert state.current_battle.npc_point == 17
    assert state.current_battle.outcome == RoundOutcome.WIN
    assert state.player.won_cards == [other]
    assert state.player.discard == [yuriko]


def test_stepwise_nested_copy_hand_choose_finalizes_points_after_last_choice():
    mirai = Card(
        "c14",
        "未来",
        "みらい",
        Janken.ROCK,
        12,
        Effect(EffectType.COPY_EFFECT, "copy deck", None),
    )
    yayoi = Card(
        "c5", "やよい", "やよい", Janken.PAPER, 15, Effect(EffectType.BUFF, "+5", 5)
    )
    anna = Card(
        "c24",
        "杏奈",
        "あんな",
        Janken.ROCK,
        17,
        Effect(EffectType.COPY_HAND, "copy hand", None),
    )
    yuriko = Card(
        "c26",
        "百合子",
        "ゆりこ",
        Janken.PAPER,
        15,
        Effect(EffectType.CHOOSE, "choose", None),
    )
    state = GameState(
        player=PlayerState(hand=[anna, yuriko]),
        npc=PlayerState(hand=[mirai], deck=[yayoi]),
    )

    state = resolve_round_stepwise(state, anna, mirai)
    state = continue_round_effect_step(state)
    state = continue_round_effect_step(state)
    state = continue_round_effect_step(state)
    state = resume_round_effect_stepwise(state, choice=yuriko.id)
    state = continue_round_effect_step(state)
    state = resume_round_effect_stepwise(state, choice="gain_points")

    assert state.phase == Phase.REVEAL
    assert state.current_battle.player_point == 20
    assert state.current_battle.npc_point == 17
    assert state.current_battle.outcome == RoundOutcome.WIN
    assert state.player.won_cards == [mirai]
    assert state.player.discard == [anna]


def test_resolve_npc_pending_effects_progresses_reorder_without_stop():
    akane = Card(
        "card_23",
        "茜",
        "あかね",
        Janken.PAPER,
        13,
        Effect(EffectType.REORDER, "reorder", None),
    )
    other = Card("cx", "other", "おざー", Janken.PAPER, 14, None)
    n1 = Card("n1", "npc1", "えぬ1", Janken.ROCK, 1)
    n2 = Card("n2", "npc2", "えぬ2", Janken.SCISSORS, 2)
    n3 = Card("n3", "npc3", "えぬ3", Janken.PAPER, 3)
    state = GameState(
        player=PlayerState(hand=[other]),
        npc=PlayerState(hand=[akane], deck=[n1, n2, n3]),
    )

    random.seed(0)
    state = resolve_round(state, other, akane)
    assert state.phase == Phase.INTERACTIVE_EFFECT
    assert state.pending_effect_context.side == Side.NPC

    state = resolve_npc_pending_effects(state, FirstChoiceStrategy())

    assert state.phase == Phase.REVEAL
    assert [card.id for card in state.npc.deck] != ["n1", "n2", "n3"]


def test_npc_interactive_effect_is_resolved_by_strategy():
    yuriko = Card(
        "c26",
        "百合子",
        "ゆりこ",
        Janken.PAPER,
        15,
        Effect(EffectType.CHOOSE, "choose", None),
    )
    other = Card("cx", "other", "おざー", Janken.PAPER, 17, None)
    state = GameState(
        player=PlayerState(hand=[other]),
        npc=PlayerState(hand=[yuriko]),
    )

    state = resolve_round(state, other, yuriko)
    assert state.phase == Phase.INTERACTIVE_EFFECT

    state = resolve_npc_pending_effects(state, FirstChoiceStrategy())

    assert state.phase == Phase.REVEAL
    assert state.current_battle.player_point == 17
    assert state.current_battle.npc_point == 18
    assert state.current_battle.outcome == RoundOutcome.LOSE


def test_conditional_debuff_draw_applies_debuff_and_draws_when_won():
    miya = Card(
        "card_42",
        "美也",
        "みや",
        Janken.PAPER,
        12,
        Effect(EffectType.CONDITIONAL_DEBUFF_DRAW, "conditional -5 then draw", -5),
    )
    opponent = Card("n1", "相手", "あいて", Janken.PAPER, 15, None)
    draw_card = Card("d1", "山札", "やまふだ", Janken.ROCK, 3, None)
    state = GameState(
        player=PlayerState(hand=[miya], deck=[draw_card]),
        npc=PlayerState(hand=[opponent]),
    )

    state = resolve_round(state, miya, opponent)

    assert state.current_battle.outcome == RoundOutcome.WIN
    assert state.current_battle.npc_point == 10
    assert state.player.hand == [draw_card]
    assert state.player.deck == []


def test_conditional_debuff_draw_skips_debuff_when_opponent_point_is_high():
    miya = Card(
        "card_42",
        "美也",
        "みや",
        Janken.PAPER,
        12,
        Effect(EffectType.CONDITIONAL_DEBUFF_DRAW, "conditional -5 then draw", -5),
    )
    opponent = Card("n1", "相手", "あいて", Janken.PAPER, 16, None)
    draw_card = Card("d1", "山札", "やまふだ", Janken.ROCK, 3, None)
    state = GameState(
        player=PlayerState(hand=[miya], deck=[draw_card], point_modifier=5),
        npc=PlayerState(hand=[opponent]),
    )

    state = resolve_round(state, miya, opponent)

    assert state.current_battle.outcome == RoundOutcome.WIN
    assert state.current_battle.npc_point == 16
    assert state.player.hand == [draw_card]


def test_conditional_debuff_draw_does_not_draw_when_not_won():
    miya = Card(
        "card_42",
        "美也",
        "みや",
        Janken.PAPER,
        12,
        Effect(EffectType.CONDITIONAL_DEBUFF_DRAW, "conditional -5 then draw", -5),
    )
    opponent = Card("n1", "相手", "あいて", Janken.PAPER, 15, None)
    draw_card = Card("d1", "山札", "やまふだ", Janken.ROCK, 3, None)
    state = GameState(
        player=PlayerState(hand=[miya], deck=[draw_card], point_modifier=-3),
        npc=PlayerState(hand=[opponent]),
    )

    state = resolve_round(state, miya, opponent)

    assert state.current_battle.outcome == RoundOutcome.LOSE
    assert state.current_battle.npc_point == 10
    assert state.player.hand == []
    assert state.player.deck == [draw_card]


def test_copied_card_18_effect_applies_on_loss():
    copy_effect_card = Card(
        "copy",
        "copy",
        "こぴー",
        Janken.ROCK,
        10,
        Effect(EffectType.COPY_EFFECT, "copy", None),
    )
    copied_elena = Card(
        "card_18",
        "エレナ",
        "えれな",
        Janken.ROCK,
        12,
        Effect(EffectType.DEBUFF_CONDITIONAL, "lose then next -3", -3),
    )
    npc_card = Card("n1", "n1", "えぬ1", Janken.ROCK, 12, None)
    state = GameState(
        player=PlayerState(hand=[copy_effect_card], deck=[copied_elena]),
        npc=PlayerState(hand=[npc_card]),
    )

    state = resolve_round(state, copy_effect_card, npc_card)

    assert state.current_battle.outcome == RoundOutcome.LOSE
    assert state.npc.next_round_conditional_point_modifier_non_wildcard == -3
