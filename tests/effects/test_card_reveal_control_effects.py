from shadow_bout.engine import (
    proceed_to_next,
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
    Side,
)


def test_curse_sets_must_reveal_state_on_opponent():
    curse = Card(
        "c51",
        "呪い",
        "のろい",
        Janken.ROCK,
        10,
        Effect(EffectType.CURSE, "curse", None),
    )
    other = Card("cx", "other", "おざー", Janken.ROCK, 9, None)
    state = GameState(
        player=PlayerState(hand=[curse]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, curse, other)

    assert state.npc.must_reveal_played_card is True


def test_reveal_marks_npc_hand_card_as_persistent_public():
    roco = Card(
        "c25",
        "ロコ",
        "ろこ",
        Janken.ROCK,
        15,
        Effect(EffectType.REVEAL, "reveal", None),
    )
    other = Card("cx", "other", "おざー", Janken.ROCK, 18, None)
    n_extra = Card("n_extra", "n_extra", "ん", Janken.PAPER, 1)
    state = GameState(
        player=PlayerState(hand=[roco]),
        npc=PlayerState(hand=[other, n_extra]),
    )

    state = resolve_round(state, roco, other)

    assert state.phase == Phase.REVEAL
    assert state.npc.revealed_card_ids == frozenset({n_extra.id})


def test_reveal_all_marks_npc_hand_cards_as_persistent_public():
    takane = Card(
        "c08",
        "貴音",
        "たかね",
        Janken.SCISSORS,
        15,
        Effect(EffectType.REVEAL_ALL, "reveal all", None),
    )
    other = Card("cx", "other", "おざー", Janken.SCISSORS, 18, None)
    p_extra = Card("p_extra", "p_extra", "ぴ", Janken.PAPER, 1)
    n_extra = Card("n_extra", "n_extra", "ん", Janken.PAPER, 1)
    state = GameState(
        player=PlayerState(hand=[takane, p_extra]),
        npc=PlayerState(hand=[other, n_extra]),
    )

    state = resolve_round(state, takane, other)

    assert state.phase == Phase.REVEAL
    assert state.revealed_this_round == [n_extra]
    assert state.revealed_this_round_side == Side.NPC
    assert state.npc.revealed_card_ids == frozenset({n_extra.id})

    next_state = proceed_to_next(state)

    assert next_state.phase == Phase.SELECT
    assert next_state.revealed_this_round is None
    assert next_state.revealed_this_round_side is None
    assert next_state.npc.revealed_card_ids == frozenset({n_extra.id})


def test_npc_reveal_all_marks_player_hand_cards_as_persistent_public():
    takane = Card(
        "c08",
        "貴音",
        "たかね",
        Janken.SCISSORS,
        15,
        Effect(EffectType.REVEAL_ALL, "reveal all", None),
    )
    other = Card("cx", "other", "おざー", Janken.SCISSORS, 18, None)
    p_extra = Card("p_extra", "p_extra", "ぴ", Janken.PAPER, 1)
    state = GameState(
        player=PlayerState(hand=[other, p_extra]),
        npc=PlayerState(hand=[takane]),
    )

    state = resolve_round(state, other, takane)

    assert state.phase == Phase.REVEAL
    assert state.revealed_this_round == [p_extra]
    assert state.revealed_this_round_side == Side.PLAYER
    assert state.player.revealed_card_ids == frozenset({p_extra.id})


def test_takane_draw_reveals_both_remaining_hands_persistently():
    player_takane = Card(
        "p_c08",
        "貴音",
        "たかね",
        Janken.SCISSORS,
        15,
        Effect(EffectType.REVEAL_ALL, "reveal all", None),
    )
    npc_takane = Card(
        "n_c08",
        "貴音",
        "たかね",
        Janken.SCISSORS,
        15,
        Effect(EffectType.REVEAL_ALL, "reveal all", None),
    )
    p_extra = Card("p_extra", "p_extra", "ぴ", Janken.PAPER, 1)
    n_extra = Card("n_extra", "n_extra", "ん", Janken.PAPER, 1)
    state = GameState(
        player=PlayerState(hand=[player_takane, p_extra]),
        npc=PlayerState(hand=[npc_takane, n_extra]),
    )

    state = resolve_round(state, player_takane, npc_takane)

    assert state.phase == Phase.REVEAL
    assert state.player.revealed_card_ids == frozenset({p_extra.id})
    assert state.npc.revealed_card_ids == frozenset({n_extra.id})

    next_state = proceed_to_next(state)

    assert next_state.player.revealed_card_ids == frozenset({p_extra.id})
    assert next_state.npc.revealed_card_ids == frozenset({n_extra.id})


def test_force_play_sets_forced_card_id_on_opponent_side():
    tamaki = Card(
        "c12",
        "環",
        "たまき",
        Janken.ROCK,
        13,
        Effect(EffectType.FORCE_PLAY, "force play", None),
    )
    other = Card("cx", "other", "おざー", Janken.ROCK, 13, None)
    n_extra = Card("n_extra", "n_extra", "ん", Janken.PAPER, 1)
    state = GameState(
        player=PlayerState(hand=[tamaki]),
        npc=PlayerState(hand=[other, n_extra]),
    )

    state = resolve_round(state, tamaki, other)

    assert state.npc.forced_card_id == n_extra.id


def test_npc_force_play_sets_forced_card_id_on_player_side():
    tamaki = Card(
        "c12",
        "環",
        "たまき",
        Janken.ROCK,
        13,
        Effect(EffectType.FORCE_PLAY, "force play", None),
    )
    other = Card("cx", "other", "おざー", Janken.ROCK, 13, None)
    p_extra = Card("p_extra", "p_extra", "ぴ", Janken.SCISSORS, 1)
    state = GameState(
        player=PlayerState(hand=[other, p_extra]),
        npc=PlayerState(hand=[tamaki]),
    )

    state = resolve_round(state, other, tamaki)

    assert state.player.forced_card_id == p_extra.id


def test_force_play_is_safe_when_opponent_has_no_hand():
    tamaki = Card(
        "c12",
        "環",
        "たまき",
        Janken.ROCK,
        13,
        Effect(EffectType.FORCE_PLAY, "force play", None),
    )
    other = Card("cx", "other", "おざー", Janken.ROCK, 13, None)
    state = GameState(
        player=PlayerState(hand=[tamaki]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, tamaki, other)

    assert state.npc.forced_card_id is None


def test_ban_adds_banned_card_id_on_opponent_side():
    kaori = Card(
        "card_52",
        "歌織",
        "かおり",
        Janken.ROCK,
        14,
        Effect(EffectType.BAN, "ban", None),
    )
    other = Card("cx", "other", "おざー", Janken.ROCK, 13, None)
    n_extra = Card("n_extra", "n_extra", "ん", Janken.PAPER, 1)
    state = GameState(
        player=PlayerState(hand=[kaori]),
        npc=PlayerState(hand=[other, n_extra]),
    )

    state = resolve_round(state, kaori, other)

    assert state.npc.banned_card_ids == frozenset({n_extra.id})


def test_ban_clears_forced_card_id_when_target_is_forced_card():
    kaori = Card(
        "card_52",
        "歌織",
        "かおり",
        Janken.ROCK,
        14,
        Effect(EffectType.BAN, "ban", None),
    )
    other = Card("cx", "other", "おざー", Janken.ROCK, 13, None)
    forced = Card("forced", "forced", "ふぉーす", Janken.PAPER, 1)
    state = GameState(
        player=PlayerState(hand=[kaori]),
        npc=PlayerState(hand=[other, forced], forced_card_id=forced.id),
    )

    state = resolve_round(state, kaori, other)

    assert state.npc.banned_card_ids == frozenset({forced.id})
    assert state.npc.forced_card_id is None


def test_immune_blocks_opponent_reveal_all_and_force_play():
    emily = Card(
        "card_32",
        "エミリー",
        "えみりー",
        Janken.ROCK,
        13,
        Effect(EffectType.IMMUNE, "immune", None),
    )
    extra = Card("extra", "extra", "えくすとら", Janken.PAPER, 1, None)
    takane = Card(
        "card_08",
        "貴音",
        "たかね",
        Janken.ROCK,
        15,
        Effect(EffectType.REVEAL_ALL, "reveal all", None),
    )
    force = Card(
        "card_12",
        "真美",
        "まみ",
        Janken.ROCK,
        12,
        Effect(EffectType.FORCE_PLAY, "force play", None),
    )

    reveal_state = resolve_round(
        GameState(
            player=PlayerState(hand=[emily, extra]),
            npc=PlayerState(hand=[takane]),
        ),
        emily,
        takane,
    )
    force_state = resolve_round(
        GameState(
            player=PlayerState(hand=[emily, extra]),
            npc=PlayerState(hand=[force]),
        ),
        emily,
        force,
    )

    assert reveal_state.player.revealed_card_ids == frozenset()
    assert reveal_state.revealed_this_round is None
    assert reveal_state.revealed_this_round_side is None
    assert force_state.player.forced_card_id is None
