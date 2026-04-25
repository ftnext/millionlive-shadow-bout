import pytest

from shadow_bout.engine import (
    check_forfeit,
    compare_points,
    init_game,
    judge_janken,
)
from shadow_bout.models import Card, Janken, JankenResult, RoundOutcome, Side


@pytest.fixture
def mock_cards():
    return [
        Card("c1", "R10", Janken.ROCK, 10),
        Card("c2", "S10", Janken.SCISSORS, 10),
        Card("c3", "P10", Janken.PAPER, 10),
        Card("c4", "R20", Janken.ROCK, 20),
    ]


def test_judge_janken(mock_cards):
    r, s, p, _ = mock_cards
    assert judge_janken(r, s) == JankenResult.WIN
    assert judge_janken(s, p) == JankenResult.WIN
    assert judge_janken(p, r) == JankenResult.WIN
    assert judge_janken(r, p) == JankenResult.LOSE
    assert judge_janken(r, r) == JankenResult.DRAW


def test_compare_points(mock_cards):
    r10, _, _, r20 = mock_cards
    # base_point only
    # 10 vs 20 -> LOSE
    assert compare_points(r10, r20) == RoundOutcome.LOSE
    # 20 vs 10 -> WIN
    assert compare_points(r20, r10) == RoundOutcome.WIN
    # 10 vs 10 -> EVEN
    assert compare_points(r10, r10) == RoundOutcome.EVEN


def test_init_game(mock_cards):
    deck = mock_cards * 4  # 16 cards
    state = init_game(deck)
    assert len(state.player.hand) == 5
    assert len(state.npc.hand) == 5
    assert len(state.player.deck) == 11
    assert len(state.npc.deck) == 11


def test_check_forfeit(mock_cards):
    from shadow_bout.models import PlayerState

    p_empty = PlayerState(hand=[])
    p_has = PlayerState(hand=mock_cards)

    assert check_forfeit(p_empty, p_has) == Side.PLAYER
    assert check_forfeit(p_has, p_empty) == Side.NPC
    assert check_forfeit(p_has, p_has) is None
    assert check_forfeit(p_empty, p_empty) is None
