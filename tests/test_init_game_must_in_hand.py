import random

import pytest

from shadow_bout.engine import init_game, start_game
from shadow_bout.models import Card, Janken, Phase


def _make_deck(size: int) -> list[Card]:
    return [
        Card(f"card_{i:02d}", f"name{i}", f"kana{i}", Janken.ROCK, 10)
        for i in range(size)
    ]


def test_player_must_in_hand_always_in_starting_hand():
    deck = _make_deck(14)
    must = [deck[0]]

    for seed in range(50):
        random.seed(seed)
        state = init_game(deck, player_must_in_hand=must)
        hand_ids = {c.id for c in state.player.hand}
        assert must[0].id in hand_ids, f"seed {seed}: lead missing from hand"
        assert len(state.player.hand) == 5
        assert len(state.player.deck) == len(deck) - 5


def test_npc_must_in_hand_always_in_starting_hand():
    p_deck = _make_deck(14)
    n_deck = _make_deck(13)
    p_must = [p_deck[0]]
    n_must = [n_deck[0]]

    for seed in range(50):
        random.seed(seed)
        state = init_game(
            p_deck,
            n_deck,
            player_must_in_hand=p_must,
            npc_must_in_hand=n_must,
        )
        assert p_must[0].id in {c.id for c in state.player.hand}
        assert n_must[0].id in {c.id for c in state.npc.hand}
        assert len(state.npc.hand) == 5
        assert len(state.npc.deck) == len(n_deck) - 5


def test_must_in_hand_card_not_in_deck_is_silently_ignored():
    deck = _make_deck(13)
    foreign = Card("foreign_id", "x", "x", Janken.ROCK, 10)
    state = init_game(deck, player_must_in_hand=[foreign])
    assert len(state.player.hand) == 5
    assert all(c.id != foreign.id for c in state.player.hand)


def test_start_game_propagates_must_in_hand():
    deck = _make_deck(14)
    must = [deck[0]]
    random.seed(0)
    state = start_game(deck, player_must_in_hand=must)
    assert state.phase == Phase.SELECT
    assert must[0].id in {c.id for c in state.player.hand}


def test_must_in_hand_default_none_preserves_existing_behavior():
    deck = _make_deck(13)
    random.seed(123)
    state = init_game(deck)
    assert len(state.player.hand) == 5
    assert len(state.player.deck) == 8
    assert len(state.npc.hand) == 5
    assert len(state.npc.deck) == 8


def test_multiple_required_cards_all_land_in_hand():
    deck = _make_deck(14)
    must = [deck[0], deck[1], deck[2]]
    for seed in range(20):
        random.seed(seed)
        state = init_game(deck, player_must_in_hand=must)
        hand_ids = {c.id for c in state.player.hand}
        for required in must:
            assert required.id in hand_ids


@pytest.mark.parametrize("seed", range(20))
def test_must_in_hand_does_not_duplicate_cards(seed):
    deck = _make_deck(14)
    must = [deck[0]]
    random.seed(seed)
    state = init_game(deck, player_must_in_hand=must)
    all_ids = [c.id for c in state.player.hand] + [c.id for c in state.player.deck]
    assert len(all_ids) == len(deck)
    assert len(set(all_ids)) == len(deck)
