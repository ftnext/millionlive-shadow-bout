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
