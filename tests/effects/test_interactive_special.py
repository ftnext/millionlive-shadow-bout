from shadow_bout.engine import (
    resolve_npc_pending_effects,
    resolve_round,
    resume_round_effect,
)
from shadow_bout.models import (
    Card,
    Effect,
    EffectType,
    GameState,
    Janken,
    Phase,
    PlayerState,
)
from tests.effects.helpers import FirstChoiceStrategy


def test_special_steals_opponent_won_card_when_declared_mark_matches_revealed_hand():
    miki = Card(
        "card_03",
        "美希",
        "みき",
        Janken.ROCK,
        16,
        Effect(EffectType.SPECIAL, "special", None),
    )
    opponent = Card("op", "相手", "あいて", Janken.ROCK, 16, None)
    revealed = Card("n_hand", "相手手札", "あいててふだ", Janken.PAPER, 1, None)
    own_deck = Card("p_deck", "自分山札", "じぶんやまふだ", Janken.ROCK, 1, None)
    won_keep = Card("n_won1", "相手勝ち札1", "あいてかちふだ1", Janken.ROCK, 2, None)
    won_steal = Card(
        "n_won2", "相手勝ち札2", "あいてかちふだ2", Janken.SCISSORS, 3, None
    )
    state = GameState(
        player=PlayerState(hand=[miki], deck=[own_deck]),
        npc=PlayerState(hand=[opponent, revealed], won_cards=[won_keep, won_steal]),
    )

    state = resolve_round(state, miki, opponent)
    assert state.phase == Phase.INTERACTIVE_EFFECT

    state = resume_round_effect(state, choice=Janken.PAPER.value)
    assert state.phase == Phase.INTERACTIVE_EFFECT
    assert state.pending_effect_context.effect == "special"
    assert state.pending_effect_context.step == 1

    state = resume_round_effect(state, choice=won_steal.id)

    assert state.phase == Phase.REVEAL
    assert state.player.deck == [own_deck, won_steal]
    assert state.npc.won_cards == [won_keep]


def test_special_steals_only_one_won_card_when_same_id_exists():
    miki = Card(
        "card_03",
        "美希",
        "みき",
        Janken.ROCK,
        16,
        Effect(EffectType.SPECIAL, "special", None),
    )
    opponent = Card("op", "相手", "あいて", Janken.ROCK, 16, None)
    revealed = Card("n_hand", "相手手札", "あいててふだ", Janken.PAPER, 1, None)
    won_a = Card("same_won", "相手勝ち札A", "あいてかちふだA", Janken.ROCK, 2, None)
    won_b = Card("same_won", "相手勝ち札B", "あいてかちふだB", Janken.SCISSORS, 3, None)
    state = GameState(
        player=PlayerState(hand=[miki]),
        npc=PlayerState(hand=[opponent, revealed], won_cards=[won_a, won_b]),
    )

    state = resolve_round(state, miki, opponent)
    state = resume_round_effect(state, choice=Janken.PAPER.value)
    state = resume_round_effect(state, choice=won_a.id)

    assert state.player.deck == [won_a]
    assert state.npc.won_cards == [won_b]


def test_special_does_not_steal_when_declared_mark_mismatches_revealed_hand():
    miki = Card(
        "card_03",
        "美希",
        "みき",
        Janken.ROCK,
        16,
        Effect(EffectType.SPECIAL, "special", None),
    )
    opponent = Card("op", "相手", "あいて", Janken.ROCK, 16, None)
    revealed = Card("n_hand", "相手手札", "あいててふだ", Janken.SCISSORS, 1, None)
    won = Card("n_won", "相手勝ち札", "あいてかちふだ", Janken.ROCK, 2, None)
    state = GameState(
        player=PlayerState(hand=[miki]),
        npc=PlayerState(hand=[opponent, revealed], won_cards=[won]),
    )

    state = resolve_round(state, miki, opponent)
    state = resume_round_effect(state, choice=Janken.PAPER.value)

    assert state.phase == Phase.REVEAL
    assert state.player.deck == []
    assert state.npc.won_cards == [won]
    assert any("一致しないため奪取なし" in log for log in state.battle_log)


def test_special_does_not_steal_when_opponent_has_no_won_cards():
    miki = Card(
        "card_03",
        "美希",
        "みき",
        Janken.ROCK,
        16,
        Effect(EffectType.SPECIAL, "special", None),
    )
    opponent = Card("op", "相手", "あいて", Janken.ROCK, 16, None)
    revealed = Card("n_hand", "相手手札", "あいててふだ", Janken.PAPER, 1, None)
    state = GameState(
        player=PlayerState(hand=[miki]),
        npc=PlayerState(hand=[opponent, revealed], won_cards=[]),
    )

    state = resolve_round(state, miki, opponent)
    state = resume_round_effect(state, choice=Janken.PAPER.value)

    assert state.phase == Phase.REVEAL
    assert state.player.deck == []
    assert state.npc.won_cards == []
    assert any("相手の勝ち札がないため奪取できない" in log for log in state.battle_log)


def test_npc_special_declares_and_steals_with_strategy():
    miki = Card(
        "card_03",
        "美希",
        "みき",
        Janken.ROCK,
        16,
        Effect(EffectType.SPECIAL, "special", None),
    )
    player_card = Card("op", "相手", "あいて", Janken.ROCK, 16, None)
    player_hand = Card("p_hand", "プレイヤー手札", "ぷれいやーてふだ", Janken.ROCK, 1)
    player_won = Card(
        "p_won", "プレイヤー勝ち札", "ぷれいやーかちふだ", Janken.PAPER, 2
    )
    state = GameState(
        player=PlayerState(hand=[player_card, player_hand], won_cards=[player_won]),
        npc=PlayerState(hand=[miki]),
    )

    state = resolve_round(state, player_card, miki)
    state = resolve_npc_pending_effects(state, FirstChoiceStrategy())

    assert state.phase == Phase.REVEAL
    assert state.player.won_cards == []
    assert state.npc.deck == [player_won]
