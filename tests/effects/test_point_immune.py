from shadow_bout.engine import (
    resolve_round,
)
from shadow_bout.models import (
    Card,
    Effect,
    EffectType,
    GameState,
    Janken,
    PlayerState,
)


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
