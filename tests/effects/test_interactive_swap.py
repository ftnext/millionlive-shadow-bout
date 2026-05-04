import random

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
    Side,
)
from tests.effects.helpers import FirstChoiceStrategy, LastChoiceStrategy


def test_swap_opponent_effect_swaps_with_random_opponent_hand_card():
    random.seed(0)
    kana = Card(
        "card_36",
        "可奈",
        "かな",
        Janken.PAPER,
        13,
        Effect(EffectType.SWAP_OPPONENT, "swap opponent", None),
    )
    npc_card = Card("n_battle", "n_battle", "えぬ場", Janken.PAPER, 10, None)
    hand1 = Card("n_h1", "n_h1", "えぬ手1", Janken.ROCK, 2, None)
    hand2 = Card("n_h2", "n_h2", "えぬ手2", Janken.SCISSORS, 3, None)
    state = GameState(
        player=PlayerState(hand=[kana]),
        npc=PlayerState(hand=[npc_card, hand1, hand2]),
    )

    state = resolve_round(state, kana, npc_card)
    state = resume_round_effect(state, choice="reveal")
    state = resume_round_effect(state, choice="swap")

    assert state.current_battle.npc_card.id in {hand1.id, hand2.id}
    assert npc_card in state.npc.hand
    assert len(state.npc.hand) == 2


def test_swap_opponent_effect_can_skip():
    kana = Card(
        "card_36",
        "可奈",
        "かな",
        Janken.PAPER,
        13,
        Effect(EffectType.SWAP_OPPONENT, "swap opponent", None),
    )
    npc_card = Card("n_battle", "n_battle", "えぬ場", Janken.PAPER, 10, None)
    hand1 = Card("n_h1", "n_h1", "えぬ手1", Janken.ROCK, 2, None)
    state = GameState(
        player=PlayerState(hand=[kana]),
        npc=PlayerState(hand=[npc_card, hand1]),
    )

    state = resolve_round(state, kana, npc_card)
    state = resume_round_effect(state, choice="reveal")
    state = resume_round_effect(state, choice=None)

    assert state.current_battle.npc_card == npc_card
    assert state.npc.hand == [hand1]


def test_swap_opponent_effect_noops_when_opponent_hand_is_empty():
    kana = Card(
        "card_36",
        "可奈",
        "かな",
        Janken.PAPER,
        13,
        Effect(EffectType.SWAP_OPPONENT, "swap opponent", None),
    )
    npc_card = Card("n_battle", "n_battle", "えぬ場", Janken.PAPER, 10, None)
    state = GameState(
        player=PlayerState(hand=[kana]),
        npc=PlayerState(hand=[npc_card]),
    )

    state = resolve_round(state, kana, npc_card)
    state = resume_round_effect(state, choice="swap")

    assert state.current_battle.npc_card == npc_card
    assert state.npc.hand == []


def test_tutor_play_swaps_deck_card_into_battle_without_triggering_effect():
    reika = Card(
        "card_48",
        "麗花",
        "れいか",
        Janken.PAPER,
        13,
        Effect(EffectType.TUTOR_PLAY, "tutor play", None),
    )
    target = Card(
        "target",
        "強化札",
        "きょうかふだ",
        Janken.ROCK,
        30,
        Effect(EffectType.BUFF, "buff", 99),
    )
    remain = Card("remain", "残り札", "のこりふだ", Janken.SCISSORS, 1, None)
    other = Card("other", "相手札", "あいてふだ", Janken.PAPER, 20, None)
    state = GameState(
        player=PlayerState(hand=[reika], deck=[target, remain]),
        npc=PlayerState(hand=[other]),
    )

    random.seed(0)
    state = resolve_round(state, reika, other)
    assert state.phase == Phase.INTERACTIVE_EFFECT

    state = resume_round_effect(state, choice=target.id)

    assert state.phase == Phase.REVEAL
    assert state.current_battle.player_card == target
    assert state.current_battle.player_point == 30
    assert state.player.point_modifier == 0
    assert target not in state.player.deck
    assert {card.id for card in state.player.deck} == {"card_48", "remain"}
    assert target in state.player.discard
    assert not any("強化札の効果発動" in log for log in state.battle_log)


def test_tutor_play_skip_keeps_battle_card_and_deck_unchanged_by_effect():
    reika = Card(
        "card_48",
        "麗花",
        "れいか",
        Janken.PAPER,
        13,
        Effect(EffectType.TUTOR_PLAY, "tutor play", None),
    )
    d1 = Card("d1", "山札1", "やまふだ1", Janken.ROCK, 1, None)
    d2 = Card("d2", "山札2", "やまふだ2", Janken.SCISSORS, 2, None)
    other = Card("other", "相手札", "あいてふだ", Janken.PAPER, 20, None)
    state = GameState(
        player=PlayerState(hand=[reika], deck=[d1, d2]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, reika, other)
    assert state.phase == Phase.INTERACTIVE_EFFECT

    state = resume_round_effect(state, choice="skip")

    assert state.phase == Phase.REVEAL
    assert state.current_battle.player_card == reika
    assert state.player.deck == [d1, d2]
    assert reika in state.npc.won_cards


def test_tutor_play_can_select_self_when_deck_is_empty():
    reika = Card(
        "card_48",
        "麗花",
        "れいか",
        Janken.PAPER,
        13,
        Effect(EffectType.TUTOR_PLAY, "tutor play", None),
    )
    other = Card("other", "相手札", "あいてふだ", Janken.PAPER, 20, None)
    state = GameState(
        player=PlayerState(hand=[reika], deck=[]),
        npc=PlayerState(hand=[other]),
    )

    state = resolve_round(state, reika, other)
    assert state.phase == Phase.INTERACTIVE_EFFECT

    state = resume_round_effect(state, choice=reika.id)

    assert state.phase == Phase.REVEAL
    assert state.current_battle.player_card == reika
    assert state.player.deck == []
    assert reika in state.npc.won_cards


def test_resolve_npc_pending_effects_progresses_tutor_play():
    reika = Card(
        "card_48",
        "麗花",
        "れいか",
        Janken.PAPER,
        13,
        Effect(EffectType.TUTOR_PLAY, "tutor play", None),
    )
    target = Card("target", "強い札", "つよいふだ", Janken.ROCK, 30, None)
    remain = Card("remain", "残り札", "のこりふだ", Janken.SCISSORS, 1, None)
    other = Card("other", "相手札", "あいてふだ", Janken.PAPER, 20, None)
    state = GameState(
        player=PlayerState(hand=[other]),
        npc=PlayerState(hand=[reika], deck=[target, remain]),
    )

    random.seed(0)
    state = resolve_round(state, other, reika)
    assert state.phase == Phase.INTERACTIVE_EFFECT
    assert state.pending_effect_context.side == Side.NPC

    state = resolve_npc_pending_effects(state, FirstChoiceStrategy())

    assert state.phase == Phase.REVEAL
    assert state.current_battle.npc_card == target
    assert state.current_battle.npc_point == 30
    assert target not in state.npc.deck
    assert {card.id for card in state.npc.deck} == {"card_48", "remain"}


def test_npc_copy_hand_tutor_play_self_candidate_uses_battle_card():
    anna = Card(
        "card_24",
        "杏奈",
        "あんな",
        Janken.PAPER,
        17,
        Effect(EffectType.COPY_HAND, "copy hand", None),
    )
    reika = Card(
        "card_48",
        "麗花",
        "れいか",
        Janken.PAPER,
        13,
        Effect(EffectType.TUTOR_PLAY, "tutor play", None),
    )
    deck_card = Card("deck", "山札", "やまふだ", Janken.ROCK, 1, None)
    other = Card("other", "相手札", "あいてふだ", Janken.PAPER, 20, None)
    state = GameState(
        player=PlayerState(hand=[other]),
        npc=PlayerState(hand=[anna, reika], deck=[deck_card]),
    )

    random.seed(0)
    state = resolve_round(state, other, anna)
    assert state.phase == Phase.INTERACTIVE_EFFECT
    assert state.pending_effect_context.effect == "copy_hand"

    state = resolve_npc_pending_effects(state, LastChoiceStrategy())

    assert state.phase == Phase.REVEAL
    assert state.current_battle.npc_card == anna
    assert state.npc.deck == [deck_card]
    assert any("杏奈を場に出し直し" in log for log in state.battle_log)
