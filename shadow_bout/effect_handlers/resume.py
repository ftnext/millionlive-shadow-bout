from shadow_bout.effect_handlers.common import _finish_interactive_effect
from shadow_bout.effect_handlers.resume_battle import (
    _resume_removal,
    _resume_special,
)
from shadow_bout.effect_handlers.resume_cards import (
    _resume_reorder,
    _resume_salvage,
    _resume_search_and_swap,
    _resume_swap,
    _resume_swap_opponent,
    _resume_tutor_play,
)
from shadow_bout.effect_handlers.resume_choices import (
    _resume_choose,
    _resume_choose_multiple,
    _resume_copy_hand,
    _resume_debuff_counterable,
    _resume_set_point_match,
)
from shadow_bout.models import GameState


def resume_pending_effect(state: GameState, choice: str | None = None) -> GameState:
    ctx = state.pending_effect_context
    if not ctx:
        return state

    side = ctx.side
    if ctx.effect == "choose":
        return _resume_choose(state, side, choice)
    if ctx.effect == "copy_hand":
        return _resume_copy_hand(state, side, choice)
    if ctx.effect == "search_and_swap":
        return _resume_search_and_swap(state, side, choice)
    if ctx.effect == "swap":
        return _resume_swap(state, side, choice)
    if ctx.effect == "tutor_play":
        return _resume_tutor_play(state, side, choice)
    if ctx.effect == "swap_opponent":
        return _resume_swap_opponent(state, side, choice)
    if ctx.effect == "removal":
        return _resume_removal(state, side, choice)
    if ctx.effect == "set_point_match":
        return _resume_set_point_match(state, side, choice)
    if ctx.effect == "salvage":
        return _resume_salvage(state, side, choice)
    if ctx.effect == "reorder":
        return _resume_reorder(state, side, choice)
    if ctx.effect == "choose_multiple":
        return _resume_choose_multiple(state, side, choice)
    if ctx.effect == "debuff_counterable":
        return _resume_debuff_counterable(state, side, choice)
    if ctx.effect == "special":
        return _resume_special(state, side, choice)

    return _finish_interactive_effect(state, "-> 選択完了")
