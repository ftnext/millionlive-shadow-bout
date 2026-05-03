from dataclasses import replace

from shadow_bout.models import GameState, PlayerState, Side


def update_player(state: GameState, side: Side, **kwargs) -> GameState:
    if side == Side.PLAYER:
        new_p = replace(state.player, **kwargs)
        return replace(state, player=new_p)

    new_n = replace(state.npc, **kwargs)
    return replace(state, npc=new_n)


def get_player_state(state: GameState, side: Side) -> PlayerState:
    return state.player if side == Side.PLAYER else state.npc


def get_opponent_side(side: Side) -> Side:
    return Side.NPC if side == Side.PLAYER else Side.PLAYER


def add_banned_card_id(state: GameState, side: Side, card_id: str) -> GameState:
    player_state = get_player_state(state, side)
    return update_player(
        state,
        side,
        banned_card_ids=player_state.banned_card_ids | {card_id},
    )


def set_forced_card_id(state: GameState, side: Side, card_id: str | None) -> GameState:
    return update_player(state, side, forced_card_id=card_id)


def clear_forced_card_id(state: GameState, side: Side) -> GameState:
    return set_forced_card_id(state, side, None)


def set_must_reveal_played_card(
    state: GameState, side: Side, should_reveal: bool
) -> GameState:
    return update_player(state, side, must_reveal_played_card=should_reveal)


def set_must_reveal_played_card_rounds(
    state: GameState, side: Side, rounds: int
) -> GameState:
    return update_player(
        state,
        side,
        must_reveal_played_card_rounds=max(0, rounds),
    )
