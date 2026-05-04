import random
from dataclasses import replace

from shadow_bout.effect_handlers.common import (
    _opponent_is_immune,
)
from shadow_bout.effect_handlers.registry import register
from shadow_bout.effect_utils import (
    get_opponent_side,
    get_player_state,
    update_player,
)
from shadow_bout.models import (
    Card,
    GameState,
    Side,
)


@register("draw")
def effect_draw(state: GameState, side: Side, card: Card) -> GameState:
    if card.id in ("card_01", "c1"):
        own_state = get_player_state(state, side)
        own_merged_deck = own_state.deck + own_state.hand
        random.shuffle(own_merged_deck)
        own_draw_count = int(card.effect.value or 0)
        own_drawn = own_merged_deck[:own_draw_count]
        state = update_player(
            state,
            side,
            hand=own_drawn,
            deck=own_merged_deck[len(own_drawn) :],
        )

        opp_side = get_opponent_side(side)
        if _opponent_is_immune(state, side):
            return replace(
                state,
                battle_log=state.battle_log
                + [
                    f"{card.name}の効果発動: 自分は{len(own_drawn)}枚ドロー。相手は戦具効果を受けないため対象外"
                ],
            )

        opp_state = get_player_state(state, opp_side)
        opp_merged_deck = opp_state.deck + opp_state.hand
        random.shuffle(opp_merged_deck)
        opp_draw_count = int(card.effect.value or 0)
        opp_drawn = opp_merged_deck[:opp_draw_count]
        state = update_player(
            state,
            opp_side,
            hand=opp_drawn,
            deck=opp_merged_deck[len(opp_drawn) :],
        )

        return replace(
            state,
            battle_log=state.battle_log
            + [
                f"{card.name}の効果発動: お互いの手札を山札に戻して切り、自分は{len(own_drawn)}枚、相手は{len(opp_drawn)}枚ドロー"
            ],
        )

    draw_count = int(card.effect.value or 0)
    own_state = get_player_state(state, side)
    own_drawn = own_state.deck[:draw_count]
    state = update_player(
        state,
        side,
        hand=own_state.hand + own_drawn,
        deck=own_state.deck[len(own_drawn) :],
    )

    opp_side = get_opponent_side(side)
    if _opponent_is_immune(state, side):
        return replace(
            state,
            battle_log=state.battle_log
            + [
                f"{card.name}の効果発動: 自分は{len(own_drawn)}枚ドロー。相手は戦具効果を受けないため対象外"
            ],
        )

    opp_state = get_player_state(state, opp_side)
    opp_drawn = opp_state.deck[:draw_count]
    state = update_player(
        state,
        opp_side,
        hand=opp_state.hand + opp_drawn,
        deck=opp_state.deck[len(opp_drawn) :],
    )

    return replace(
        state,
        battle_log=state.battle_log
        + [
            f"{card.name}の効果発動: 自分は{len(own_drawn)}枚、相手は{len(opp_drawn)}枚ドロー"
        ],
    )


@register("draw_dynamic")
def effect_draw_dynamic(state: GameState, side: Side, card: Card) -> GameState:
    own_state = get_player_state(state, side)
    moved_count = len(own_state.discard)

    if moved_count == 0:
        return replace(
            state,
            battle_log=state.battle_log + [f"{card.name}の効果発動: 捨札がなく不発"],
        )

    new_deck = own_state.deck + own_state.discard
    random.shuffle(new_deck)
    drawn = new_deck[:moved_count]
    state = update_player(
        state,
        side,
        hand=own_state.hand + drawn,
        deck=new_deck[len(drawn) :],
        discard=[],
    )
    return replace(
        state,
        battle_log=state.battle_log
        + [
            f"{card.name}の効果発動: 捨札{moved_count}枚を山札に戻して{len(drawn)}枚ドロー"
        ],
    )
