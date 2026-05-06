from dataclasses import replace

import pytest

from shadow_bout.engine import (
    apply_battle_result,
    check_forfeit,
    compare_points,
    init_game,
    judge_janken,
    proceed_to_next,
    resolve_round,
    select_card,
)
from shadow_bout.models import (
    BattleJankenOverride,
    BattleResult,
    Card,
    CompletedRound,
    Effect,
    EffectType,
    GameState,
    Janken,
    JankenResult,
    PendingEffectContext,
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


class FirstCardStrategy:
    def select_card(self, hand, game_state):
        return hand[0]


class PaperWildcardStrategy(FirstCardStrategy):
    def choose_effect(self, choices, game_state):
        return Janken.PAPER.value

    def declare_wildcard_janken(self, choices, game_state):
        return Janken.PAPER.value


def test_select_card_rejects_banned_player_card(mock_cards):
    p1, p2, n1, _ = mock_cards
    state = GameState(
        player=PlayerState(hand=[p1, p2], banned_card_ids=frozenset({p1.id})),
        npc=PlayerState(hand=[n1]),
        phase=Phase.SELECT,
    )

    with pytest.raises(ValueError, match="cannot play banned card"):
        select_card(state, p1, FirstCardStrategy())


def test_select_card_rejects_non_forced_player_card(mock_cards):
    p1, p2, n1, _ = mock_cards
    state = GameState(
        player=PlayerState(hand=[p1, p2], forced_card_id=p2.id),
        npc=PlayerState(hand=[n1]),
        phase=Phase.SELECT,
    )

    with pytest.raises(ValueError, match="must play forced card"):
        select_card(state, p1, FirstCardStrategy())


def test_select_card_rejects_player_card_not_in_hand(mock_cards):
    p1, p2, n1, _ = mock_cards
    state = GameState(
        player=PlayerState(hand=[p1]),
        npc=PlayerState(hand=[n1]),
        phase=Phase.SELECT,
    )

    with pytest.raises(ValueError, match="selected card is not in hand"):
        select_card(state, p2, FirstCardStrategy())


def test_select_card_applies_npc_forced_play(mock_cards):
    p1, n1, n2, _ = mock_cards
    state = GameState(
        player=PlayerState(hand=[p1]),
        npc=PlayerState(hand=[n1, n2], forced_card_id=n2.id),
        phase=Phase.SELECT,
    )

    next_state = select_card(state, p1, FirstCardStrategy())

    assert all(card.id != n2.id for card in next_state.npc.hand)
    assert next_state.npc.forced_card_id is None


def test_select_card_allows_play_when_forced_card_is_no_longer_in_hand(mock_cards):
    p1, p2, n1, _ = mock_cards
    state = GameState(
        player=PlayerState(hand=[p1, p2], forced_card_id="missing-card-id"),
        npc=PlayerState(hand=[n1]),
        phase=Phase.SELECT,
    )

    next_state = select_card(state, p1, FirstCardStrategy())

    assert next_state.phase == Phase.REVEAL
    assert next_state.player.forced_card_id is None


def test_select_card_rejects_when_npc_has_no_playable_card(mock_cards):
    p1, n1, _, _ = mock_cards
    state = GameState(
        player=PlayerState(hand=[p1]),
        npc=PlayerState(hand=[n1], banned_card_ids=frozenset({n1.id})),
        phase=Phase.SELECT,
    )

    with pytest.raises(ValueError, match="npc has no playable cards"):
        select_card(state, p1, FirstCardStrategy())


def test_select_card_without_constraints_keeps_current_behavior(mock_cards):
    p1, n1, _, _ = mock_cards
    state = GameState(
        player=PlayerState(hand=[p1]),
        npc=PlayerState(hand=[n1]),
        phase=Phase.SELECT,
    )

    next_state = select_card(state, p1, FirstCardStrategy())

    assert next_state.phase == Phase.REVEAL


def test_judge_janken(mock_cards):
    r, s, p, _ = mock_cards
    assert judge_janken(r, s) == JankenResult.WIN
    assert judge_janken(s, p) == JankenResult.WIN
    assert judge_janken(p, r) == JankenResult.WIN
    assert judge_janken(r, p) == JankenResult.LOSE
    assert judge_janken(r, r) == JankenResult.DRAW


@pytest.mark.parametrize(
    ("declared_janken", "npc_janken"),
    [
        (Janken.ROCK, Janken.SCISSORS),
        (Janken.SCISSORS, Janken.PAPER),
        (Janken.PAPER, Janken.ROCK),
    ],
)
def test_resolve_round_wildcard_uses_declared_janken(declared_janken, npc_janken):
    momoko = Card(
        "card_49",
        "桃子",
        "ももこ",
        Janken.WILDCARD,
        6,
        Effect(EffectType.WILDCARD, "wildcard", None),
    )
    npc_card = Card("npc", "NPC", "えぬぴーしー", npc_janken, 10)
    state = GameState(
        player=PlayerState(hand=[momoko]),
        npc=PlayerState(hand=[npc_card]),
        phase=Phase.SELECT,
    )

    next_state = resolve_round(
        state,
        momoko,
        npc_card,
        player_wildcard_janken=declared_janken,
    )

    assert next_state.current_battle.janken_result == JankenResult.WIN
    assert next_state.current_battle.outcome == RoundOutcome.WIN
    assert next_state.battle_janken_overrides == (
        BattleJankenOverride(Side.PLAYER, momoko.id, declared_janken),
    )


def test_select_card_auto_declares_npc_wildcard():
    player_card = Card("player", "Player", "ぷれいやー", Janken.ROCK, 10)
    momoko = Card(
        "card_49",
        "桃子",
        "ももこ",
        Janken.WILDCARD,
        6,
        Effect(EffectType.WILDCARD, "wildcard", None),
    )
    state = GameState(
        player=PlayerState(hand=[player_card]),
        npc=PlayerState(hand=[momoko]),
        phase=Phase.SELECT,
    )

    next_state = select_card(state, player_card, PaperWildcardStrategy())

    assert next_state.current_battle.janken_result == JankenResult.LOSE
    assert next_state.current_battle.outcome == RoundOutcome.LOSE
    assert next_state.battle_janken_overrides == (
        BattleJankenOverride(Side.NPC, momoko.id, Janken.PAPER),
    )


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


def test_init_game_with_separate_npc_deck():
    p_deck = [
        Card("p1", "P1", "k", Janken.ROCK, 10),
        Card("p2", "P2", "k", Janken.SCISSORS, 10),
        Card("p3", "P3", "k", Janken.PAPER, 10),
        Card("p4", "P4", "k", Janken.ROCK, 10),
        Card("p5", "P5", "k", Janken.SCISSORS, 10),
        Card("p6", "P6", "k", Janken.PAPER, 10),
        Card("p7", "P7", "k", Janken.ROCK, 10),
    ]
    n_deck = [
        Card("n1", "N1", "k", Janken.ROCK, 10),
        Card("n2", "N2", "k", Janken.SCISSORS, 10),
        Card("n3", "N3", "k", Janken.PAPER, 10),
        Card("n4", "N4", "k", Janken.ROCK, 10),
        Card("n5", "N5", "k", Janken.SCISSORS, 10),
        Card("n6", "N6", "k", Janken.PAPER, 10),
        Card("n7", "N7", "k", Janken.ROCK, 10),
    ]

    state = init_game(p_deck, n_deck)

    player_ids = {c.id for c in state.player.hand + state.player.deck}
    npc_ids = {c.id for c in state.npc.hand + state.npc.deck}
    assert player_ids == {c.id for c in p_deck}
    assert npc_ids == {c.id for c in n_deck}
    assert player_ids.isdisjoint(npc_ids)


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


def test_apply_battle_result_appends_to_completed_rounds(mock_cards):
    p_card, n_card, p_stock, n_stock = mock_cards
    state = GameState(
        player=PlayerState(hand=[p_card], draw_stock=[p_stock]),
        npc=PlayerState(hand=[n_card], draw_stock=[n_stock]),
        round_number=1,
    )
    win_result = BattleResult(
        outcome=RoundOutcome.WIN,
        winning_side=Side.PLAYER,
        player_card=p_card,
        npc_card=n_card,
        janken_result=JankenResult.WIN,
    )

    after_win = apply_battle_result(state, win_result)

    assert state.completed_rounds == ()
    assert after_win.completed_rounds == (
        CompletedRound(round_number=1, battle=win_result),
    )

    after_win = replace(after_win, round_number=2)
    even_result = BattleResult(
        outcome=RoundOutcome.EVEN,
        winning_side=None,
        player_card=p_stock,
        npc_card=n_stock,
        janken_result=JankenResult.DRAW,
    )
    after_even = apply_battle_result(after_win, even_result)

    assert after_even.completed_rounds == (
        CompletedRound(round_number=1, battle=win_result),
        CompletedRound(round_number=2, battle=even_result),
    )
    assert after_even.current_battle == even_result


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
        pending_effect_context=PendingEffectContext(
            side=Side.PLAYER,
            card_id=p_card.id,
            effect="choose",
            step=2,
        ),
        effect_queue=[(Side.PLAYER, p_card)],
        removal_activated=True,
        revealed_this_round=[revealed_card],
        revealed_this_round_side=Side.PLAYER,
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
    assert new_state.revealed_this_round_side is None
    assert new_state.player.point_modifier == 0
    assert new_state.player.effect_negated is False
    assert new_state.player.revealed_card_ids == frozenset({revealed_card.id})
    assert new_state.npc.point_modifier == 0
    assert new_state.npc.effect_negated is False
    assert new_state.npc.revealed_card_ids == frozenset({p_card.id})


def test_resolve_round_consumes_must_reveal_played_card_and_records_reveal(mock_cards):
    p1, n1, _, _ = mock_cards
    state = GameState(
        player=PlayerState(hand=[p1]),
        npc=PlayerState(hand=[n1], must_reveal_played_card=True),
        phase=Phase.SELECT,
    )

    next_state = resolve_round(state, p1, n1)

    assert next_state.npc.must_reveal_played_card is False
    assert next_state.revealed_this_round == [n1]
    assert next_state.revealed_this_round_side == Side.NPC


def test_resolve_round_consumes_must_reveal_played_card_rounds(mock_cards):
    p1, n1, p2, n2 = mock_cards
    state = GameState(
        player=PlayerState(hand=[p1, p2]),
        npc=PlayerState(hand=[n1, n2], must_reveal_played_card_rounds=2),
        phase=Phase.SELECT,
    )

    round_1 = resolve_round(state, p1, n1)
    assert round_1.revealed_this_round == [n1]
    assert round_1.npc.must_reveal_played_card_rounds == 1

    round_2_start = proceed_to_next(round_1)
    round_2 = resolve_round(round_2_start, p2, n2)
    assert round_2.revealed_this_round == [n2]
    assert round_2.npc.must_reveal_played_card_rounds == 0


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
    assert new_state.completed_rounds == (
        CompletedRound(round_number=2, forfeiting_side=Side.PLAYER),
        CompletedRound(round_number=3, forfeiting_side=Side.PLAYER),
        CompletedRound(round_number=4, forfeiting_side=Side.PLAYER),
    )


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


def test_proceed_to_next_applies_carryover_once_on_round_start(mock_cards):
    p_card, n_card, _, _ = mock_cards
    state = GameState(
        player=PlayerState(hand=[p_card], next_round_point_modifier=2),
        npc=PlayerState(hand=[n_card], next_round_point_modifier=-1),
        round_number=1,
        phase=Phase.REVEAL,
    )

    next_state = proceed_to_next(state)
    assert next_state.round_number == 2
    assert next_state.phase == Phase.SELECT
    assert next_state.player.point_modifier == 2
    assert next_state.npc.point_modifier == -1
    assert next_state.player.next_round_point_modifier == 0
    assert next_state.npc.next_round_point_modifier == 0

    third_state = proceed_to_next(next_state)
    assert third_state.round_number == 3
    assert third_state.player.point_modifier == 0
    assert third_state.npc.point_modifier == 0


def test_proceed_to_next_consumes_carryover_on_forfeit_round(mock_cards):
    forfeited_1, npc_card, _, _ = mock_cards
    state = GameState(
        player=PlayerState(hand=[], deck=[forfeited_1], next_round_point_modifier=4),
        npc=PlayerState(hand=[npc_card], next_round_point_modifier=-2),
        round_number=1,
        phase=Phase.REVEAL,
    )

    new_state = proceed_to_next(state)

    assert new_state.phase == Phase.RESULT
    assert new_state.round_number == 4
    assert new_state.player.next_round_point_modifier == 0
    assert new_state.npc.next_round_point_modifier == 0
    assert "R2: 持ち越し効果適用 あなた ポイント+4" in new_state.battle_log
    assert "R2: 持ち越し効果適用 NPC ポイント-2" in new_state.battle_log
