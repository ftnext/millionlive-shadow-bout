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

    state = resume_round_effect(state, choice="buff")

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
    state = resume_round_effect_stepwise(state, choice="buff")

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
    state = resume_round_effect(state, choice="draw")

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
    assert state.player.persistent_point_effects == (-2,)

    next_state = proceed_to_next(state)
    assert next_state.round_number == 2
    assert next_state.player.point_modifier == -2
    assert next_state.player.persistent_point_effects == ()

    third_state = proceed_to_next(next_state)
    assert third_state.round_number == 3
    assert third_state.player.point_modifier == 0
