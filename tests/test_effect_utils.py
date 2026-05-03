from shadow_bout.effect_utils import (
    add_banned_card_id,
    clear_forced_card_id,
    set_forced_card_id,
    set_must_reveal_played_card,
)
from shadow_bout.models import GameState, PlayerState, Side


def test_add_banned_card_id_updates_only_target_side() -> None:
    state = GameState(player=PlayerState(), npc=PlayerState())

    next_state = add_banned_card_id(state, Side.PLAYER, "card-001")

    assert next_state.player.banned_card_ids == frozenset({"card-001"})
    assert next_state.npc.banned_card_ids == frozenset()


def test_set_and_clear_forced_card_id() -> None:
    state = GameState(player=PlayerState(), npc=PlayerState())

    forced_state = set_forced_card_id(state, Side.NPC, "card-777")
    assert forced_state.npc.forced_card_id == "card-777"

    cleared_state = clear_forced_card_id(forced_state, Side.NPC)
    assert cleared_state.npc.forced_card_id is None


def test_set_must_reveal_played_card() -> None:
    state = GameState(player=PlayerState(), npc=PlayerState())

    reveal_state = set_must_reveal_played_card(state, Side.PLAYER, True)
    assert reveal_state.player.must_reveal_played_card is True

    hidden_state = set_must_reveal_played_card(reveal_state, Side.PLAYER, False)
    assert hidden_state.player.must_reveal_played_card is False
