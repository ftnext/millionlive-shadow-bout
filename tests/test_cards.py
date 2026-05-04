import random

from shadow_bout.cards import load_deck, select_random_deck


def test_select_random_deck_returns_requested_size():
    deck = select_random_deck(13)
    assert len(deck) == 13


def test_select_random_deck_no_duplicates_in_one_deck():
    deck = select_random_deck(13)
    ids = [c.id for c in deck]
    assert len(set(ids)) == len(ids)


def test_select_random_deck_picks_from_all_52_cards():
    all_cards = load_deck()
    all_ids = {c.id for c in all_cards}
    deck = select_random_deck(13)
    assert {c.id for c in deck}.issubset(all_ids)


def test_select_random_deck_two_calls_can_overlap():
    """プレイヤー / NPC それぞれ独立に抽選するので両デッキで同一カードがあり得る。"""
    random.seed(0)
    p_deck = select_random_deck(13)
    n_deck = select_random_deck(13)
    p_ids = {c.id for c in p_deck}
    n_ids = {c.id for c in n_deck}
    # シード固定で重なりが発生することを確認（実装が独立抽選であることの担保）
    assert p_ids & n_ids


def test_select_random_deck_two_calls_differ():
    random.seed(1)
    deck_a = select_random_deck(13)
    deck_b = select_random_deck(13)
    assert [c.id for c in deck_a] != [c.id for c in deck_b]
