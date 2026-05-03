from shadow_bout.effects import calculate_effective_point
from shadow_bout.engine import (
    continue_round_effect_step,
    proceed_to_next,
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
    PersistentPointEffect,
    Phase,
    PlayerState,
    RoundOutcome,
    Side,
)


class FirstChoiceStrategy:
    def select_card(self, hand, game_state):
        return hand[0]

    def choose_effect(self, choices, game_state):
        return choices[0]

    def select_target(self, candidates, game_state):
        return candidates[0]

    def should_activate(self, card, game_state):
        return True


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
    assert state.player.deck == [hand_card, draw_2]


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


def test_ami_restart():
    # 4. 亜美 restart
    ami = Card(
        "c11",
        "亜美",
        "あみ",
        Janken.SCISSORS,
        12,
        Effect(EffectType.RESTART, "restart", None),
    )
    other = Card("cx", "other", "おざー", Janken.SCISSORS, 15, None)

    state = GameState(player=PlayerState(hand=[]), npc=PlayerState(hand=[]))
    state = resolve_round(state, ami, other)

    # Should be back to Phase.SELECT
    assert state.phase == Phase.SELECT
    assert state.last_restart_round == 1
    # Cards should be back in hand
    assert ami in state.player.hand
    assert other in state.npc.hand


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


def test_curse_sets_must_reveal_state_on_opponent():
    curse = Card(
        "c51",
        "呪い",
        "のろい",
        Janken.ROCK,
        10,
        Effect(EffectType.CURSE, "curse", None),
    )
    other = Card("cx", "other", "おざー", Janken.ROCK, 9, None)
    state = GameState(
        player=PlayerState(hand=[curse]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, curse, other)

    assert state.npc.must_reveal_played_card is True


def test_karen_choose_activate_sets_must_reveal_on_opponent():
    karen = Card(
        "c45",
        "可憐",
        "かれん",
        Janken.ROCK,
        10,
        Effect(EffectType.CHOOSE, "choose", None),
    )
    other = Card("cx", "other", "おざー", Janken.ROCK, 9, None)
    state = GameState(
        player=PlayerState(hand=[karen]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, karen, other)
    assert state.phase == Phase.INTERACTIVE_EFFECT

    state = resume_round_effect(state, choice="activate")

    assert state.npc.must_reveal_played_card is False
    assert state.npc.must_reveal_played_card_rounds == 2


def test_ami_restart_does_not_duplicate_played_cards():
    ami = Card(
        "c11",
        "亜美",
        "あみ",
        Janken.SCISSORS,
        12,
        Effect(EffectType.RESTART, "restart", None),
    )
    other = Card("cx", "other", "おざー", Janken.SCISSORS, 15, None)
    p_extra = Card("p_extra", "p_extra", "ぴ", Janken.ROCK, 1)
    n_extra = Card("n_extra", "n_extra", "ん", Janken.PAPER, 1)
    state = GameState(
        player=PlayerState(hand=[ami, p_extra]),
        npc=PlayerState(hand=[other, n_extra]),
    )

    state = resolve_round(state, ami, other)

    assert state.phase == Phase.SELECT
    assert state.player.hand == [p_extra, ami]
    assert state.npc.hand == [n_extra, other]


def test_ami_consecutive_restart():
    # 5. 亜美の連続使用不可
    ami = Card(
        "c11",
        "亜美",
        "あみ",
        Janken.SCISSORS,
        12,
        Effect(EffectType.RESTART, "restart", None),
    )
    other = Card("cx", "other", "おざー", Janken.SCISSORS, 15, None)

    state = GameState(
        player=PlayerState(hand=[]),
        npc=PlayerState(hand=[]),
        last_restart_round=0,  # Mock that it happened last round (round 1 - 1 = 0)
    )
    state = resolve_round(state, ami, other)

    # Should NOT restart. ami wins because 12 < 15? Wait, outcome determined by points.
    # Ami = 12, Other = 15. Other wins. Player loses.
    assert state.phase == Phase.REVEAL
    assert state.current_battle.outcome == RoundOutcome.LOSE


def test_reveal_marks_npc_hand_card_as_persistent_public():
    roco = Card(
        "c25",
        "ロコ",
        "ろこ",
        Janken.ROCK,
        15,
        Effect(EffectType.REVEAL, "reveal", None),
    )
    other = Card("cx", "other", "おざー", Janken.ROCK, 18, None)
    n_extra = Card("n_extra", "n_extra", "ん", Janken.PAPER, 1)
    state = GameState(
        player=PlayerState(hand=[roco]),
        npc=PlayerState(hand=[other, n_extra]),
    )

    state = resolve_round(state, roco, other)

    assert state.phase == Phase.REVEAL
    assert state.npc.revealed_card_ids == frozenset({n_extra.id})


def test_reveal_all_marks_npc_hand_cards_as_persistent_public():
    takane = Card(
        "c08",
        "貴音",
        "たかね",
        Janken.SCISSORS,
        15,
        Effect(EffectType.REVEAL_ALL, "reveal all", None),
    )
    other = Card("cx", "other", "おざー", Janken.SCISSORS, 18, None)
    p_extra = Card("p_extra", "p_extra", "ぴ", Janken.PAPER, 1)
    n_extra = Card("n_extra", "n_extra", "ん", Janken.PAPER, 1)
    state = GameState(
        player=PlayerState(hand=[takane, p_extra]),
        npc=PlayerState(hand=[other, n_extra]),
    )

    state = resolve_round(state, takane, other)

    assert state.phase == Phase.REVEAL
    assert state.revealed_this_round == [n_extra]
    assert state.revealed_this_round_side == Side.NPC
    assert state.npc.revealed_card_ids == frozenset({n_extra.id})

    next_state = proceed_to_next(state)

    assert next_state.phase == Phase.SELECT
    assert next_state.revealed_this_round is None
    assert next_state.revealed_this_round_side is None
    assert next_state.npc.revealed_card_ids == frozenset({n_extra.id})


def test_npc_reveal_all_marks_player_hand_cards_as_persistent_public():
    takane = Card(
        "c08",
        "貴音",
        "たかね",
        Janken.SCISSORS,
        15,
        Effect(EffectType.REVEAL_ALL, "reveal all", None),
    )
    other = Card("cx", "other", "おざー", Janken.SCISSORS, 18, None)
    p_extra = Card("p_extra", "p_extra", "ぴ", Janken.PAPER, 1)
    state = GameState(
        player=PlayerState(hand=[other, p_extra]),
        npc=PlayerState(hand=[takane]),
    )

    state = resolve_round(state, other, takane)

    assert state.phase == Phase.REVEAL
    assert state.revealed_this_round == [p_extra]
    assert state.revealed_this_round_side == Side.PLAYER
    assert state.player.revealed_card_ids == frozenset({p_extra.id})


def test_takane_draw_reveals_both_remaining_hands_persistently():
    player_takane = Card(
        "p_c08",
        "貴音",
        "たかね",
        Janken.SCISSORS,
        15,
        Effect(EffectType.REVEAL_ALL, "reveal all", None),
    )
    npc_takane = Card(
        "n_c08",
        "貴音",
        "たかね",
        Janken.SCISSORS,
        15,
        Effect(EffectType.REVEAL_ALL, "reveal all", None),
    )
    p_extra = Card("p_extra", "p_extra", "ぴ", Janken.PAPER, 1)
    n_extra = Card("n_extra", "n_extra", "ん", Janken.PAPER, 1)
    state = GameState(
        player=PlayerState(hand=[player_takane, p_extra]),
        npc=PlayerState(hand=[npc_takane, n_extra]),
    )

    state = resolve_round(state, player_takane, npc_takane)

    assert state.phase == Phase.REVEAL
    assert state.player.revealed_card_ids == frozenset({p_extra.id})
    assert state.npc.revealed_card_ids == frozenset({n_extra.id})

    next_state = proceed_to_next(state)

    assert next_state.player.revealed_card_ids == frozenset({p_extra.id})
    assert next_state.npc.revealed_card_ids == frozenset({n_extra.id})


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


def test_force_play_sets_forced_card_id_on_opponent_side():
    tamaki = Card(
        "c12",
        "環",
        "たまき",
        Janken.ROCK,
        13,
        Effect(EffectType.FORCE_PLAY, "force play", None),
    )
    other = Card("cx", "other", "おざー", Janken.ROCK, 13, None)
    n_extra = Card("n_extra", "n_extra", "ん", Janken.PAPER, 1)
    state = GameState(
        player=PlayerState(hand=[tamaki]),
        npc=PlayerState(hand=[other, n_extra]),
    )

    state = resolve_round(state, tamaki, other)

    assert state.npc.forced_card_id == n_extra.id


def test_npc_force_play_sets_forced_card_id_on_player_side():
    tamaki = Card(
        "c12",
        "環",
        "たまき",
        Janken.ROCK,
        13,
        Effect(EffectType.FORCE_PLAY, "force play", None),
    )
    other = Card("cx", "other", "おざー", Janken.ROCK, 13, None)
    p_extra = Card("p_extra", "p_extra", "ぴ", Janken.SCISSORS, 1)
    state = GameState(
        player=PlayerState(hand=[other, p_extra]),
        npc=PlayerState(hand=[tamaki]),
    )

    state = resolve_round(state, other, tamaki)

    assert state.player.forced_card_id == p_extra.id


def test_force_play_is_safe_when_opponent_has_no_hand():
    tamaki = Card(
        "c12",
        "環",
        "たまき",
        Janken.ROCK,
        13,
        Effect(EffectType.FORCE_PLAY, "force play", None),
    )
    other = Card("cx", "other", "おざー", Janken.ROCK, 13, None)
    state = GameState(
        player=PlayerState(hand=[tamaki]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, tamaki, other)

    assert state.npc.forced_card_id is None


def test_ban_adds_banned_card_id_on_opponent_side():
    kaori = Card(
        "card_52",
        "歌織",
        "かおり",
        Janken.ROCK,
        14,
        Effect(EffectType.BAN, "ban", None),
    )
    other = Card("cx", "other", "おざー", Janken.ROCK, 13, None)
    n_extra = Card("n_extra", "n_extra", "ん", Janken.PAPER, 1)
    state = GameState(
        player=PlayerState(hand=[kaori]),
        npc=PlayerState(hand=[other, n_extra]),
    )

    state = resolve_round(state, kaori, other)

    assert state.npc.banned_card_ids == frozenset({n_extra.id})


def test_ban_clears_forced_card_id_when_target_is_forced_card():
    kaori = Card(
        "card_52",
        "歌織",
        "かおり",
        Janken.ROCK,
        14,
        Effect(EffectType.BAN, "ban", None),
    )
    other = Card("cx", "other", "おざー", Janken.ROCK, 13, None)
    forced = Card("forced", "forced", "ふぉーす", Janken.PAPER, 1)
    state = GameState(
        player=PlayerState(hand=[kaori]),
        npc=PlayerState(hand=[other, forced], forced_card_id=forced.id),
    )

    state = resolve_round(state, kaori, other)

    assert state.npc.banned_card_ids == frozenset({forced.id})
    assert state.npc.forced_card_id is None
