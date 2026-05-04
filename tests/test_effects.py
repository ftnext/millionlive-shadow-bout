import random

from shadow_bout.effects import calculate_effective_point
from shadow_bout.engine import (
    continue_round_effect_step,
    proceed_to_next,
    process_next_effect,
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
    JankenResult,
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


class LastChoiceStrategy(FirstChoiceStrategy):
    def select_target(self, candidates, game_state):
        return candidates[-1]


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


def test_immune_blocks_karen_choose_reveal_effect_on_resume():
    karen = Card(
        "card_45",
        "可憐",
        "かれん",
        Janken.SCISSORS,
        11,
        Effect(EffectType.CHOOSE, "choose", None),
    )
    emily = Card(
        "card_32",
        "エミリー",
        "えみりー",
        Janken.SCISSORS,
        13,
        Effect(EffectType.IMMUNE, "immune", None),
    )
    state = GameState(
        player=PlayerState(hand=[karen]),
        npc=PlayerState(hand=[emily]),
    )

    state = resolve_round(state, karen, emily)
    assert state.phase == Phase.INTERACTIVE_EFFECT

    state = resume_round_effect(state, choice="activate")

    assert state.npc.must_reveal_played_card_rounds == 0
    assert any(
        "可憐の効果: 相手は戦具効果を受けないため不発" in log
        for log in state.battle_log
    )


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


def test_ami_restart_clears_pending_conditional_debuff_on_loss():
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
        player=PlayerState(hand=[ami]),
        npc=PlayerState(hand=[other]),
        pending_conditional_debuff_on_loss=((Side.PLAYER, -3),),
    )

    state = resolve_round(state, ami, other)

    assert state.phase == Phase.SELECT
    assert state.pending_conditional_debuff_on_loss == ()


def test_ami_restart_clears_pending_snowball_buff_on_win():
    snowball = Card(
        "snowball",
        "このみ効果",
        "このみこうか",
        Janken.SCISSORS,
        10,
        Effect(EffectType.BUFF_SNOWBALL, "this +3 and win next +3", 3),
    )
    ami = Card(
        "c11",
        "亜美",
        "あみ",
        Janken.SCISSORS,
        12,
        Effect(EffectType.RESTART, "restart", None),
    )
    state = GameState(
        player=PlayerState(hand=[snowball]),
        npc=PlayerState(hand=[ami]),
    )

    state = resolve_round(state, snowball, ami)

    assert state.phase == Phase.SELECT
    assert state.pending_next_round_buff_on_win == ()


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


def test_steal_draw_effect_moves_top_card_from_opponent_deck_to_own_hand():
    serika = Card(
        "card_22",
        "星梨花",
        "せりか",
        Janken.ROCK,
        13,
        Effect(EffectType.STEAL_DRAW, "steal draw", 1),
    )
    other = Card("cx", "other", "おざー", Janken.ROCK, 13, None)
    stolen = Card("n1", "n1", "えぬ1", Janken.PAPER, 1)
    remain = Card("n2", "n2", "えぬ2", Janken.SCISSORS, 2)
    state = GameState(
        player=PlayerState(hand=[serika]),
        npc=PlayerState(hand=[other], deck=[stolen, remain]),
    )

    state = resolve_round(state, serika, other)

    assert state.player.hand == [stolen]
    assert state.npc.deck == [remain]


def test_steal_draw_effect_noops_when_opponent_deck_is_empty():
    serika = Card(
        "card_22",
        "星梨花",
        "せりか",
        Janken.ROCK,
        13,
        Effect(EffectType.STEAL_DRAW, "steal draw", 1),
    )
    other = Card("cx", "other", "おざー", Janken.ROCK, 13, None)
    state = GameState(
        player=PlayerState(hand=[serika]),
        npc=PlayerState(hand=[other], deck=[]),
    )

    state = resolve_round(state, serika, other)

    assert state.player.hand == []
    assert state.npc.deck == []


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


def test_steal_hand_effect_moves_random_card_from_opponent_hand_to_own_hand():
    random.seed(0)
    rio = Card(
        "card_46",
        "莉緒",
        "りお",
        Janken.SCISSORS,
        11,
        Effect(EffectType.STEAL_HAND, "steal hand", 1),
    )
    other = Card("cx", "other", "おざー", Janken.SCISSORS, 11, None)
    n1 = Card("n1", "n1", "えぬ1", Janken.PAPER, 1)
    n2 = Card("n2", "n2", "えぬ2", Janken.ROCK, 2)
    state = GameState(
        player=PlayerState(hand=[rio]),
        npc=PlayerState(hand=[other, n1, n2]),
    )

    state = resolve_round(state, rio, other)

    assert state.player.hand == [n2]
    assert state.npc.hand == [n1]


def test_steal_hand_effect_noops_when_opponent_hand_is_empty():
    rio = Card(
        "card_46",
        "莉緒",
        "りお",
        Janken.SCISSORS,
        11,
        Effect(EffectType.STEAL_HAND, "steal hand", 1),
    )
    other = Card("cx", "other", "おざー", Janken.SCISSORS, 11, None)
    state = GameState(
        player=PlayerState(hand=[rio]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, rio, other)

    assert state.player.hand == []
    assert state.npc.hand == []


def test_swap_opponent_effect_swaps_with_random_opponent_hand_card():
    random.seed(0)
    kana = Card(
        "card_36",
        "可奈",
        "かな",
        Janken.PAPER,
        13,
        Effect(EffectType.SWAP_OPPONENT, "swap opponent", None),
    )
    npc_card = Card("n_battle", "n_battle", "えぬ場", Janken.PAPER, 10, None)
    hand1 = Card("n_h1", "n_h1", "えぬ手1", Janken.ROCK, 2, None)
    hand2 = Card("n_h2", "n_h2", "えぬ手2", Janken.SCISSORS, 3, None)
    state = GameState(
        player=PlayerState(hand=[kana]),
        npc=PlayerState(hand=[npc_card, hand1, hand2]),
    )

    state = resolve_round(state, kana, npc_card)
    state = resume_round_effect(state, choice="reveal")
    state = resume_round_effect(state, choice="swap")

    assert state.current_battle.npc_card.id in {hand1.id, hand2.id}
    assert npc_card in state.npc.hand
    assert len(state.npc.hand) == 2


def test_swap_opponent_effect_can_skip():
    kana = Card(
        "card_36",
        "可奈",
        "かな",
        Janken.PAPER,
        13,
        Effect(EffectType.SWAP_OPPONENT, "swap opponent", None),
    )
    npc_card = Card("n_battle", "n_battle", "えぬ場", Janken.PAPER, 10, None)
    hand1 = Card("n_h1", "n_h1", "えぬ手1", Janken.ROCK, 2, None)
    state = GameState(
        player=PlayerState(hand=[kana]),
        npc=PlayerState(hand=[npc_card, hand1]),
    )

    state = resolve_round(state, kana, npc_card)
    state = resume_round_effect(state, choice="reveal")
    state = resume_round_effect(state, choice=None)

    assert state.current_battle.npc_card == npc_card
    assert state.npc.hand == [hand1]


def test_swap_opponent_effect_noops_when_opponent_hand_is_empty():
    kana = Card(
        "card_36",
        "可奈",
        "かな",
        Janken.PAPER,
        13,
        Effect(EffectType.SWAP_OPPONENT, "swap opponent", None),
    )
    npc_card = Card("n_battle", "n_battle", "えぬ場", Janken.PAPER, 10, None)
    state = GameState(
        player=PlayerState(hand=[kana]),
        npc=PlayerState(hand=[npc_card]),
    )

    state = resolve_round(state, kana, npc_card)
    state = resume_round_effect(state, choice="swap")

    assert state.current_battle.npc_card == npc_card
    assert state.npc.hand == []


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


def test_immune_blocks_opponent_set_point_compared_with_non_immune_card():
    azusa = Card(
        "card_10",
        "あずさ",
        "あずさ",
        Janken.SCISSORS,
        10,
        Effect(EffectType.SET_POINT, "set point", 0),
    )
    emily = Card(
        "card_32",
        "エミリー",
        "えみりー",
        Janken.SCISSORS,
        13,
        Effect(EffectType.IMMUNE, "immune", None),
    )
    other = Card("other", "other", "おざー", Janken.SCISSORS, 13, None)

    immune_state = resolve_round(
        GameState(player=PlayerState(hand=[emily]), npc=PlayerState(hand=[azusa])),
        emily,
        azusa,
    )
    non_immune_state = resolve_round(
        GameState(player=PlayerState(hand=[other]), npc=PlayerState(hand=[azusa])),
        other,
        azusa,
    )

    assert immune_state.current_battle.player_point == 13
    assert non_immune_state.current_battle.player_point == 0
    assert any("戦具効果を受けないため不発" in log for log in immune_state.battle_log)


def test_immune_blocks_opponent_negate_even_before_immune_resolves():
    emily = Card(
        "card_32",
        "エミリー",
        "えみりー",
        Janken.ROCK,
        13,
        Effect(EffectType.IMMUNE, "immune", None),
    )
    chihaya = Card(
        "card_02",
        "千早",
        "ちはや",
        Janken.ROCK,
        11,
        Effect(EffectType.NEGATE, "negate", None),
    )
    state = GameState(player=PlayerState(hand=[emily]), npc=PlayerState(hand=[chihaya]))

    state = resolve_round(state, emily, chihaya)

    assert state.player.effect_negated is False
    assert any(
        "エミリーの効果発動: 相手の戦具効果を受けない" in log
        for log in state.battle_log
    )


def test_immune_blocks_opponent_reveal_all_and_force_play():
    emily = Card(
        "card_32",
        "エミリー",
        "えみりー",
        Janken.ROCK,
        13,
        Effect(EffectType.IMMUNE, "immune", None),
    )
    extra = Card("extra", "extra", "えくすとら", Janken.PAPER, 1, None)
    takane = Card(
        "card_08",
        "貴音",
        "たかね",
        Janken.ROCK,
        15,
        Effect(EffectType.REVEAL_ALL, "reveal all", None),
    )
    force = Card(
        "card_12",
        "真美",
        "まみ",
        Janken.ROCK,
        12,
        Effect(EffectType.FORCE_PLAY, "force play", None),
    )

    reveal_state = resolve_round(
        GameState(
            player=PlayerState(hand=[emily, extra]),
            npc=PlayerState(hand=[takane]),
        ),
        emily,
        takane,
    )
    force_state = resolve_round(
        GameState(
            player=PlayerState(hand=[emily, extra]),
            npc=PlayerState(hand=[force]),
        ),
        emily,
        force,
    )

    assert reveal_state.player.revealed_card_ids == frozenset()
    assert reveal_state.revealed_this_round is None
    assert reveal_state.revealed_this_round_side is None
    assert force_state.player.forced_card_id is None


def test_immune_blocks_only_opponent_side_of_mutual_draw_effect():
    haruka = Card(
        "card_01",
        "春香",
        "はるか",
        Janken.SCISSORS,
        9,
        Effect(EffectType.DRAW, "mutual draw", 2),
    )
    emily = Card(
        "card_32",
        "エミリー",
        "えみりー",
        Janken.SCISSORS,
        13,
        Effect(EffectType.IMMUNE, "immune", None),
    )
    own_deck_1 = Card("own1", "own1", "おうん1", Janken.ROCK, 1, None)
    own_deck_2 = Card("own2", "own2", "おうん2", Janken.PAPER, 1, None)
    opp_extra = Card("opp_extra", "opp_extra", "おっぷ", Janken.ROCK, 1, None)
    opp_deck = Card("opp_deck", "opp_deck", "おっぷでっき", Janken.PAPER, 1, None)
    state = GameState(
        player=PlayerState(hand=[haruka], deck=[own_deck_1, own_deck_2]),
        npc=PlayerState(hand=[emily, opp_extra], deck=[opp_deck]),
    )

    state = resolve_round(state, haruka, emily)

    assert len(state.player.hand) == 2
    assert state.npc.hand == [opp_extra]
    assert state.npc.deck == [opp_deck]


def test_tutor_play_swaps_deck_card_into_battle_without_triggering_effect():
    reika = Card(
        "card_48",
        "麗花",
        "れいか",
        Janken.PAPER,
        13,
        Effect(EffectType.TUTOR_PLAY, "tutor play", None),
    )
    target = Card(
        "target",
        "強化札",
        "きょうかふだ",
        Janken.ROCK,
        30,
        Effect(EffectType.BUFF, "buff", 99),
    )
    remain = Card("remain", "残り札", "のこりふだ", Janken.SCISSORS, 1, None)
    other = Card("other", "相手札", "あいてふだ", Janken.PAPER, 20, None)
    state = GameState(
        player=PlayerState(hand=[reika], deck=[target, remain]),
        npc=PlayerState(hand=[other]),
    )

    random.seed(0)
    state = resolve_round(state, reika, other)
    assert state.phase == Phase.INTERACTIVE_EFFECT

    state = resume_round_effect(state, choice=target.id)

    assert state.phase == Phase.REVEAL
    assert state.current_battle.player_card == target
    assert state.current_battle.player_point == 30
    assert state.player.point_modifier == 0
    assert target not in state.player.deck
    assert {card.id for card in state.player.deck} == {"card_48", "remain"}
    assert target in state.player.discard
    assert not any("強化札の効果発動" in log for log in state.battle_log)


def test_tutor_play_skip_keeps_battle_card_and_deck_unchanged_by_effect():
    reika = Card(
        "card_48",
        "麗花",
        "れいか",
        Janken.PAPER,
        13,
        Effect(EffectType.TUTOR_PLAY, "tutor play", None),
    )
    d1 = Card("d1", "山札1", "やまふだ1", Janken.ROCK, 1, None)
    d2 = Card("d2", "山札2", "やまふだ2", Janken.SCISSORS, 2, None)
    other = Card("other", "相手札", "あいてふだ", Janken.PAPER, 20, None)
    state = GameState(
        player=PlayerState(hand=[reika], deck=[d1, d2]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, reika, other)
    assert state.phase == Phase.INTERACTIVE_EFFECT

    state = resume_round_effect(state, choice="skip")

    assert state.phase == Phase.REVEAL
    assert state.current_battle.player_card == reika
    assert state.player.deck == [d1, d2]
    assert reika in state.npc.won_cards


def test_tutor_play_can_select_self_when_deck_is_empty():
    reika = Card(
        "card_48",
        "麗花",
        "れいか",
        Janken.PAPER,
        13,
        Effect(EffectType.TUTOR_PLAY, "tutor play", None),
    )
    other = Card("other", "相手札", "あいてふだ", Janken.PAPER, 20, None)
    state = GameState(
        player=PlayerState(hand=[reika], deck=[]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, reika, other)
    assert state.phase == Phase.INTERACTIVE_EFFECT

    state = resume_round_effect(state, choice=reika.id)

    assert state.phase == Phase.REVEAL
    assert state.current_battle.player_card == reika
    assert state.player.deck == []
    assert reika in state.npc.won_cards


def test_resolve_npc_pending_effects_progresses_tutor_play():
    reika = Card(
        "card_48",
        "麗花",
        "れいか",
        Janken.PAPER,
        13,
        Effect(EffectType.TUTOR_PLAY, "tutor play", None),
    )
    target = Card("target", "強い札", "つよいふだ", Janken.ROCK, 30, None)
    remain = Card("remain", "残り札", "のこりふだ", Janken.SCISSORS, 1, None)
    other = Card("other", "相手札", "あいてふだ", Janken.PAPER, 20, None)
    state = GameState(
        player=PlayerState(hand=[other]),
        npc=PlayerState(hand=[reika], deck=[target, remain]),
    )

    random.seed(0)
    state = resolve_round(state, other, reika)
    assert state.phase == Phase.INTERACTIVE_EFFECT
    assert state.pending_effect_context.side == Side.NPC

    state = resolve_npc_pending_effects(state, FirstChoiceStrategy())

    assert state.phase == Phase.REVEAL
    assert state.current_battle.npc_card == target
    assert state.current_battle.npc_point == 30
    assert target not in state.npc.deck
    assert {card.id for card in state.npc.deck} == {"card_48", "remain"}


def test_npc_copy_hand_tutor_play_self_candidate_uses_battle_card():
    anna = Card(
        "card_24",
        "杏奈",
        "あんな",
        Janken.PAPER,
        17,
        Effect(EffectType.COPY_HAND, "copy hand", None),
    )
    reika = Card(
        "card_48",
        "麗花",
        "れいか",
        Janken.PAPER,
        13,
        Effect(EffectType.TUTOR_PLAY, "tutor play", None),
    )
    deck_card = Card("deck", "山札", "やまふだ", Janken.ROCK, 1, None)
    other = Card("other", "相手札", "あいてふだ", Janken.PAPER, 20, None)
    state = GameState(
        player=PlayerState(hand=[other]),
        npc=PlayerState(hand=[anna, reika], deck=[deck_card]),
    )

    random.seed(0)
    state = resolve_round(state, other, anna)
    assert state.phase == Phase.INTERACTIVE_EFFECT
    assert state.pending_effect_context.effect == "copy_hand"

    state = resolve_npc_pending_effects(state, LastChoiceStrategy())

    assert state.phase == Phase.REVEAL
    assert state.current_battle.npc_card == anna
    assert state.npc.deck == [deck_card]
    assert any("杏奈を場に出し直し" in log for log in state.battle_log)
