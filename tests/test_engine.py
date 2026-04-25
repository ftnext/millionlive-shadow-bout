import pytest

from shadow_bout.engine import (
    apply_battle_result,
    check_forfeit,
    init_game,
    judge_janken,
)
from shadow_bout.models import (
    BattleResult,
    Card,
    GameState,
    Janken,
    JankenResult,
    PlayerState,
    RoundOutcome,
    Side,
)


@pytest.fixture
def mock_cards():
    return [
        Card("c1", "R10", "kana", Janken.ROCK, 10),
        Card("c2", "S10", "kana", Janken.SCISSORS, 10),
        Card("c3", "P10", "kana", Janken.PAPER, 10),
        Card("c4", "R20", "kana", Janken.ROCK, 20),
    ]


def test_judge_janken(mock_cards):
    r, s, p, _ = mock_cards
    assert judge_janken(r, s) == JankenResult.WIN
    assert judge_janken(s, p) == JankenResult.WIN
    assert judge_janken(p, r) == JankenResult.WIN
    assert judge_janken(r, p) == JankenResult.LOSE
    assert judge_janken(r, r) == JankenResult.DRAW


def test_init_game(mock_cards):
    deck = mock_cards * 4  # 16 cards
    state = init_game(deck)
    assert len(state.player.hand) == 5
    assert len(state.npc.hand) == 5
    assert len(state.player.deck) == 11
    assert len(state.npc.deck) == 11


def test_check_forfeit(mock_cards):
    p_empty = PlayerState(hand=[])
    p_has = PlayerState(hand=mock_cards)

    assert check_forfeit(p_empty, p_has) == Side.PLAYER
    assert check_forfeit(p_has, p_empty) == Side.NPC
    assert check_forfeit(p_has, p_has) is None
    assert check_forfeit(p_empty, p_empty) is None


def test_apply_battle_result_player_win_moves_cards_by_rule(mock_cards):
    p_card, n_card, p_stock, n_stock = mock_cards
    state = GameState(
        player=PlayerState(hand=[p_card], draw_stock=[p_stock]),
        npc=PlayerState(hand=[n_card], draw_stock=[n_stock]),
    )
    result = BattleResult(
        outcome=RoundOutcome.WIN,
        winning_side=Side.PLAYER,
        player_card=p_card,
        npc_card=n_card,
        janken_result=JankenResult.WIN,
    )

    new_state = apply_battle_result(state, result)

    assert new_state.player.hand == []
    assert new_state.npc.hand == []
    assert new_state.player.won_cards == [n_card, n_stock]
    assert new_state.player.discard == [p_card, p_stock]
    assert new_state.player.draw_stock == []
    assert new_state.npc.won_cards == []
    assert new_state.npc.discard == []
    assert new_state.npc.draw_stock == []


def test_apply_battle_result_npc_win_moves_cards_by_rule(mock_cards):
    p_card, n_card, p_stock, n_stock = mock_cards
    state = GameState(
        player=PlayerState(hand=[p_card], draw_stock=[p_stock]),
        npc=PlayerState(hand=[n_card], draw_stock=[n_stock]),
    )
    result = BattleResult(
        outcome=RoundOutcome.LOSE,
        winning_side=Side.NPC,
        player_card=p_card,
        npc_card=n_card,
        janken_result=JankenResult.LOSE,
    )

    new_state = apply_battle_result(state, result)

    assert new_state.player.hand == []
    assert new_state.npc.hand == []
    assert new_state.player.won_cards == []
    assert new_state.player.discard == []
    assert new_state.player.draw_stock == []
    assert new_state.npc.won_cards == [p_card, p_stock]
    assert new_state.npc.discard == [n_card, n_stock]
    assert new_state.npc.draw_stock == []
