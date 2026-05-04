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


def test_win_condition_overrides_point_result_when_revealed_marks_match():
    tomoka = Card(
        "card_31",
        "朋花",
        "ともか",
        Janken.ROCK,
        12,
        Effect(EffectType.WIN_CONDITION, "win condition", None),
    )
    opponent = Card("opponent", "相手", "あいて", Janken.ROCK, 20, None)
    player_top = Card("player_top", "自山パー", "じやまぱー", Janken.PAPER, 1, None)
    player_next = Card("player_next", "自山グー", "じやまぐー", Janken.ROCK, 1, None)
    npc_top = Card(
        "npc_top", "相手山チョキ", "あいてやまちょき", Janken.SCISSORS, 1, None
    )
    npc_next = Card("npc_next", "相手山グー", "あいてやまぐー", Janken.ROCK, 1, None)
    state = GameState(
        player=PlayerState(hand=[tomoka], deck=[player_top, player_next]),
        npc=PlayerState(hand=[opponent], deck=[npc_top, npc_next]),
    )

    state = resolve_round(state, tomoka, opponent)

    assert state.phase == Phase.REVEAL
    assert state.current_battle.outcome == RoundOutcome.WIN
    assert state.current_battle.winning_side == Side.PLAYER
    assert state.player.deck == [player_next, player_top]
    assert state.npc.deck == [npc_next, npc_top]
    assert state.player.won_cards == [opponent]
    assert any("勝利条件成立" in log for log in state.battle_log)


def test_win_condition_falls_back_to_normal_resolution_when_marks_do_not_match():
    tomoka = Card(
        "card_31",
        "朋花",
        "ともか",
        Janken.ROCK,
        12,
        Effect(EffectType.WIN_CONDITION, "win condition", None),
    )
    opponent = Card("opponent", "相手", "あいて", Janken.ROCK, 20, None)
    player_top = Card("player_top", "自山パー", "じやまぱー", Janken.PAPER, 1, None)
    player_next = Card("player_next", "自山グー", "じやまぐー", Janken.ROCK, 1, None)
    npc_top = Card("npc_top", "相手山グー", "あいてやまぐー", Janken.ROCK, 1, None)
    npc_next = Card(
        "npc_next", "相手山チョキ", "あいてやまちょき", Janken.SCISSORS, 1, None
    )
    state = GameState(
        player=PlayerState(hand=[tomoka], deck=[player_top, player_next]),
        npc=PlayerState(hand=[opponent], deck=[npc_top, npc_next]),
    )

    state = resolve_round(state, tomoka, opponent)

    assert state.current_battle.outcome == RoundOutcome.LOSE
    assert state.current_battle.winning_side == Side.NPC
    assert state.current_battle.player_point == 12
    assert state.current_battle.npc_point == 20
    assert state.player.deck == [player_next, player_top]
    assert state.npc.deck == [npc_next, npc_top]
    assert any("勝利条件不成立" in log for log in state.battle_log)


def test_win_condition_handles_missing_deck_without_overriding_result():
    tomoka = Card(
        "card_31",
        "朋花",
        "ともか",
        Janken.ROCK,
        12,
        Effect(EffectType.WIN_CONDITION, "win condition", None),
    )
    opponent = Card("opponent", "相手", "あいて", Janken.ROCK, 20, None)
    player_top = Card("player_top", "自山パー", "じやまぱー", Janken.PAPER, 1, None)
    player_next = Card("player_next", "自山グー", "じやまぐー", Janken.ROCK, 1, None)
    state = GameState(
        player=PlayerState(hand=[tomoka], deck=[player_top, player_next]),
        npc=PlayerState(hand=[opponent], deck=[]),
    )

    state = resolve_round(state, tomoka, opponent)

    assert state.current_battle.outcome == RoundOutcome.LOSE
    assert state.current_battle.winning_side == Side.NPC
    assert state.player.deck == [player_next, player_top]
    assert state.npc.deck == []
    assert any("山札が不足しているため不発" in log for log in state.battle_log)


def test_win_condition_handles_revealed_wildcard_as_non_matching_mark():
    tomoka = Card(
        "card_31",
        "朋花",
        "ともか",
        Janken.ROCK,
        12,
        Effect(EffectType.WIN_CONDITION, "win condition", None),
    )
    opponent = Card("opponent", "相手", "あいて", Janken.ROCK, 20, None)
    wildcard = Card(
        "card_49",
        "桃子",
        "ももこ",
        Janken.WILDCARD,
        6,
        Effect(EffectType.WILDCARD, "wildcard", None),
    )
    npc_top = Card(
        "npc_top", "相手山チョキ", "あいてやまちょき", Janken.SCISSORS, 1, None
    )
    state = GameState(
        player=PlayerState(hand=[tomoka], deck=[wildcard]),
        npc=PlayerState(hand=[opponent], deck=[npc_top]),
    )

    state = resolve_round(state, tomoka, opponent)

    assert state.current_battle.outcome == RoundOutcome.LOSE
    assert state.current_battle.winning_side == Side.NPC
    assert state.player.deck == [wildcard]
    assert state.npc.deck == [npc_top]
    assert any("桃子(ワイルド)" in log for log in state.battle_log)
    assert any("勝利条件不成立" in log for log in state.battle_log)


def test_win_condition_later_success_takes_priority_when_both_sides_succeed():
    player_tomoka = Card(
        "player_card_31",
        "朋花",
        "ともか",
        Janken.ROCK,
        12,
        Effect(EffectType.WIN_CONDITION, "win condition", None),
    )
    npc_tomoka = Card(
        "npc_card_31",
        "朋花",
        "ともか",
        Janken.ROCK,
        12,
        Effect(EffectType.WIN_CONDITION, "win condition", None),
    )
    player_top = Card("player_top", "自山パー", "じやまぱー", Janken.PAPER, 1, None)
    npc_top = Card(
        "npc_top", "相手山チョキ", "あいてやまちょき", Janken.SCISSORS, 1, None
    )
    state = GameState(
        player=PlayerState(hand=[player_tomoka], deck=[player_top]),
        npc=PlayerState(hand=[npc_tomoka], deck=[npc_top]),
    )

    state = resolve_round(state, player_tomoka, npc_tomoka)

    assert state.current_battle.outcome == RoundOutcome.LOSE
    assert state.current_battle.winning_side == Side.NPC
    assert state.npc.won_cards == [player_tomoka]
    assert sum("勝利条件成立" in log for log in state.battle_log) == 2
