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
    Phase,
    PlayerState,
    RoundOutcome,
    Side,
)


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
