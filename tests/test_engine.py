import pytest

from shadow_bout.engine import (
    apply_battle_result,
    check_forfeit,
    compare_points,
    init_game,
    judge_janken,
    proceed_to_next,
)
from shadow_bout.models import (
    BattleResult,
    Card,
    GameState,
    Janken,
    JankenResult,
    Phase,
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


def test_compare_points(mock_cards):
    low, same, _, high = mock_cards

    assert compare_points(high, low) == RoundOutcome.WIN
    assert compare_points(low, high) == RoundOutcome.LOSE
    assert compare_points(low, same) == RoundOutcome.EVEN


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


def test_proceed_to_next_resets_round_local_state(mock_cards):
    p_card, n_card, _, revealed_card = mock_cards
    battle = BattleResult(
        outcome=RoundOutcome.WIN,
        winning_side=Side.PLAYER,
        player_card=p_card,
        npc_card=n_card,
        janken_result=JankenResult.WIN,
    )
    state = GameState(
        player=PlayerState(
            hand=[p_card],
            revealed_card_ids=frozenset({revealed_card.id}),
            point_modifier=5,
            effect_negated=True,
        ),
        npc=PlayerState(
            hand=[n_card],
            revealed_card_ids=frozenset({p_card.id}),
            point_modifier=3,
            effect_negated=True,
        ),
        phase=Phase.REVEAL,
        current_battle=battle,
        last_restart_round=1,
        effect_step=2,
        pending_effect_context={"effect": "choose"},
        effect_queue=[(Side.PLAYER, p_card)],
        removal_activated=True,
        revealed_this_round=[revealed_card],
    )

    new_state = proceed_to_next(state)

    assert new_state.round_number == 2
    assert new_state.phase == Phase.SELECT
    assert new_state.current_battle is None
    assert new_state.last_restart_round == 1
    assert new_state.effect_step == 0
    assert new_state.pending_effect_context is None
    assert new_state.effect_queue == []
    assert new_state.removal_activated is False
    assert new_state.revealed_this_round is None
    assert new_state.player.point_modifier == 0
    assert new_state.player.effect_negated is False
    assert new_state.player.revealed_card_ids == frozenset({revealed_card.id})
    assert new_state.npc.point_modifier == 0
    assert new_state.npc.effect_negated is False
    assert new_state.npc.revealed_card_ids == frozenset({p_card.id})


def test_proceed_to_next_resolves_remaining_forfeit_rounds(mock_cards):
    forfeited_1, npc_card, forfeited_2, forfeited_3 = mock_cards
    state = GameState(
        player=PlayerState(hand=[], deck=[forfeited_1, forfeited_2, forfeited_3]),
        npc=PlayerState(hand=[npc_card]),
        round_number=1,
        phase=Phase.REVEAL,
    )

    new_state = proceed_to_next(state)

    assert new_state.round_number == 4
    assert new_state.phase == Phase.RESULT
    assert new_state.player.deck == []
    assert new_state.npc.won_cards == [forfeited_1, forfeited_2, forfeited_3]
    assert new_state.battle_log[-3:] == [
        "R2: あなたは不戦敗。NPCが勝ち札を獲得。",
        "R3: あなたは不戦敗。NPCが勝ち札を獲得。",
        "R4: あなたは不戦敗。NPCが勝ち札を獲得。",
    ]


def test_proceed_to_next_ends_when_both_players_cannot_play(mock_cards):
    state = GameState(
        player=PlayerState(hand=[]),
        npc=PlayerState(hand=[]),
        round_number=1,
        phase=Phase.REVEAL,
    )

    new_state = proceed_to_next(state)

    assert new_state.phase == Phase.RESULT
    assert new_state.round_number == 1
