import random
from dataclasses import replace

from shadow_bout.effect_utils import (
    get_effective_janken,
    get_player_state,
    set_battle_janken_override,
)
from shadow_bout.effects import (
    get_effect_handler,
    init_effect_resolution,
    process_next_effect,
    process_next_effect_step,
    resume_effect,
    resume_effect_step,
)
from shadow_bout.janken import judge_janken_values
from shadow_bout.models import (
    BattleResult,
    Card,
    GameState,
    Janken,
    JankenResult,
    Phase,
    PlayerState,
    RoundOutcome,
    Side,
)
from shadow_bout.npc import NpcStrategy

JANKEN_ICONS = {
    Janken.ROCK: "✊",
    Janken.SCISSORS: "✌️",
    Janken.PAPER: "✋",
    Janken.WILDCARD: "🃏",
}
JANKEN_NAMES = {
    Janken.ROCK: "グー",
    Janken.SCISSORS: "チョキ",
    Janken.PAPER: "パー",
}
WILDCARD_DECLARABLE_JANKENS = (Janken.ROCK, Janken.SCISSORS, Janken.PAPER)


def judge_janken(card_a: Card, card_b: Card) -> JankenResult:
    return judge_janken_values(card_a.janken, card_b.janken)


def judge_effective_janken(
    game_state: GameState, player_card: Card, npc_card: Card
) -> JankenResult:
    return judge_janken_values(
        get_effective_janken(game_state, Side.PLAYER, player_card),
        get_effective_janken(game_state, Side.NPC, npc_card),
    )


def compare_points(card_a: Card, card_b: Card) -> RoundOutcome:
    if card_a.base_point > card_b.base_point:
        return RoundOutcome.WIN
    if card_a.base_point < card_b.base_point:
        return RoundOutcome.LOSE
    return RoundOutcome.EVEN


def apply_battle_result(game_state: GameState, result: BattleResult) -> GameState:
    """判定結果に基づいてカード移動を実行し、新しい GameState を返す。"""
    player = game_state.player
    npc = game_state.npc

    # 元のカード（場に出されたもの）
    p_card = result.player_card
    n_card = result.npc_card

    new_p_hand = [c for c in player.hand if c.id != p_card.id]
    new_n_hand = [c for c in npc.hand if c.id != n_card.id]

    new_p_discard = list(player.discard)
    new_p_won = list(player.won_cards)
    new_p_stock = list(player.draw_stock)

    new_n_discard = list(npc.discard)
    new_n_won = list(npc.won_cards)
    new_n_stock = list(npc.draw_stock)

    if result.outcome == RoundOutcome.WIN:
        # プレイヤーの勝ち
        new_p_won.append(n_card)
        new_p_won.extend(new_n_stock)
        new_p_discard.append(p_card)
        new_p_discard.extend(new_p_stock)
        new_p_stock = []
        new_n_stock = []

    elif result.outcome == RoundOutcome.LOSE:
        # NPCの勝ち
        new_n_won.append(p_card)
        new_n_won.extend(new_p_stock)
        new_n_discard.append(n_card)
        new_n_discard.extend(new_n_stock)
        new_p_stock = []
        new_n_stock = []

    elif result.outcome == RoundOutcome.EVEN:
        # 完全引き分け
        new_p_stock.append(p_card)
        new_n_stock.append(n_card)

    new_player = replace(
        player,
        hand=new_p_hand,
        discard=new_p_discard,
        won_cards=new_p_won,
        draw_stock=new_p_stock,
    )
    new_npc = replace(
        npc,
        hand=new_n_hand,
        discard=new_n_discard,
        won_cards=new_n_won,
        draw_stock=new_n_stock,
    )

    return replace(game_state, player=new_player, npc=new_npc, current_battle=result)


def check_forfeit(player: PlayerState, npc: PlayerState) -> Side | None:
    """どちらかの手札が0枚の場合、不戦敗側を返す。両方0枚の場合は None。"""
    if not player.hand and not npc.hand:
        return None
    if not player.hand:
        return Side.PLAYER
    if not npc.hand:
        return Side.NPC
    return None


def apply_forfeit(game_state: GameState, forfeiting_side: Side) -> GameState:
    """不戦敗処理を実行し、新しい GameState を返す。"""
    player = game_state.player
    npc = game_state.npc

    if forfeiting_side == Side.PLAYER:
        # プレイヤー不戦敗: プレイヤーの山札上をNPCの勝ち札にする
        if player.deck:
            card = player.deck[0]
            new_p_deck = player.deck[1:]
            new_n_won = list(npc.won_cards) + [card]
            new_player = replace(player, deck=new_p_deck)
            new_npc = replace(npc, won_cards=new_n_won)
        else:
            new_player = player
            new_npc = npc

        return replace(game_state, player=new_player, npc=new_npc)

    else:
        # NPC不戦敗: NPCの山札上をプレイヤーの勝ち札にする
        if npc.deck:
            card = npc.deck[0]
            new_n_deck = npc.deck[1:]
            new_p_won = list(player.won_cards) + [card]
            new_player = replace(player, won_cards=new_p_won)
            new_npc = replace(npc, deck=new_n_deck)
        else:
            new_player = player
            new_npc = npc

        return replace(game_state, player=new_player, npc=new_npc)


def format_forfeit_log(round_number: int, forfeiting_side: Side) -> str:
    if forfeiting_side == Side.PLAYER:
        return f"R{round_number}: あなたは不戦敗。NPCが勝ち札を獲得。"
    return f"R{round_number}: NPCは不戦敗。あなたが勝ち札を獲得。"


def calculate_final_score(state: PlayerState) -> int:
    """勝ち札の base_point 合計"""
    return sum(card.base_point for card in state.won_cards)


def reset_round_state(game_state: GameState) -> GameState:
    """次の勝負へ持ち越さない一時状態を初期化する。"""
    new_player = replace(
        game_state.player,
        point_modifier=0,
        conditional_point_modifier_non_wildcard=0,
        janken_override=None,
        effect_negated=False,
    )
    new_npc = replace(
        game_state.npc,
        point_modifier=0,
        conditional_point_modifier_non_wildcard=0,
        janken_override=None,
        effect_negated=False,
    )
    return replace(
        game_state,
        player=new_player,
        npc=new_npc,
        current_battle=None,
        effect_step=0,
        pending_effect_context=None,
        effect_queue=[],
        removal_activated=False,
        revealed_this_round=None,
        revealed_this_round_side=None,
        pending_conditional_debuff_on_loss=(),
        pending_draw_on_win=(),
        pending_next_round_buff_on_win=(),
        point_match_effects=(),
        battle_janken_overrides=(),
    )


def apply_next_round_carryover_effects(game_state: GameState) -> GameState:
    """次ラウンド開始時に1回だけ適用して消える持ち越し効果を適用する。"""
    player_bonus = game_state.player.next_round_point_modifier
    npc_bonus = game_state.npc.next_round_point_modifier
    player_janken_override = game_state.player.next_round_janken_override
    npc_janken_override = game_state.npc.next_round_janken_override

    player_persistent_bonus = sum(
        effect.value for effect in game_state.player.persistent_point_effects
    )
    npc_persistent_bonus = sum(
        effect.value for effect in game_state.npc.persistent_point_effects
    )
    player_remaining_effects = tuple(
        replace(effect, remaining_turns=effect.remaining_turns - 1)
        for effect in game_state.player.persistent_point_effects
        if effect.remaining_turns > 1
    )
    npc_remaining_effects = tuple(
        replace(effect, remaining_turns=effect.remaining_turns - 1)
        for effect in game_state.npc.persistent_point_effects
        if effect.remaining_turns > 1
    )

    new_player = replace(
        game_state.player,
        point_modifier=(
            game_state.player.point_modifier + player_bonus + player_persistent_bonus
        ),
        next_round_point_modifier=0,
        janken_override=player_janken_override,
        conditional_point_modifier_non_wildcard=(
            game_state.player.conditional_point_modifier_non_wildcard
            + game_state.player.next_round_conditional_point_modifier_non_wildcard
        ),
        next_round_conditional_point_modifier_non_wildcard=0,
        next_round_janken_override=None,
        persistent_point_effects=player_remaining_effects,
    )
    new_npc = replace(
        game_state.npc,
        point_modifier=game_state.npc.point_modifier + npc_bonus + npc_persistent_bonus,
        next_round_point_modifier=0,
        janken_override=npc_janken_override,
        conditional_point_modifier_non_wildcard=(
            game_state.npc.conditional_point_modifier_non_wildcard
            + game_state.npc.next_round_conditional_point_modifier_non_wildcard
        ),
        next_round_conditional_point_modifier_non_wildcard=0,
        next_round_janken_override=None,
        persistent_point_effects=npc_remaining_effects,
    )

    logs: list[str] = []
    if player_bonus:
        logs.append(
            f"R{game_state.round_number}: 持ち越し効果適用 あなた ポイント{player_bonus:+d}"
        )
    if npc_bonus:
        logs.append(
            f"R{game_state.round_number}: 持ち越し効果適用 NPC ポイント{npc_bonus:+d}"
        )
    if player_persistent_bonus:
        logs.append(
            f"R{game_state.round_number}: 継続効果適用 あなた ポイント{player_persistent_bonus:+d}"
        )
    if npc_persistent_bonus:
        logs.append(
            f"R{game_state.round_number}: 継続効果適用 NPC ポイント{npc_persistent_bonus:+d}"
        )
    if player_janken_override:
        logs.append(
            f"R{game_state.round_number}: 持ち越し効果適用 あなた マークを{JANKEN_ICONS.get(player_janken_override, '')}扱い"
        )
    if npc_janken_override:
        logs.append(
            f"R{game_state.round_number}: 持ち越し効果適用 NPC マークを{JANKEN_ICONS.get(npc_janken_override, '')}扱い"
        )

    return replace(
        game_state,
        player=new_player,
        npc=new_npc,
        battle_log=game_state.battle_log + logs,
    )


def set_battle_cards_as_played(
    game_state: GameState, player_card: Card, npc_card: Card
) -> GameState:
    new_player = replace(
        game_state.player,
        hand=[card for card in game_state.player.hand if card.id != player_card.id],
        forced_card_id=None,
    )
    new_npc = replace(
        game_state.npc,
        hand=[card for card in game_state.npc.hand if card.id != npc_card.id],
        forced_card_id=None,
    )
    return replace(game_state, player=new_player, npc=new_npc)


def apply_must_reveal_played_card(
    game_state: GameState, player_card: Card, npc_card: Card
) -> GameState:
    revealed_cards: list[Card] = []
    revealed_side: Side | None = None

    player_must_reveal = (
        game_state.player.must_reveal_played_card
        or game_state.player.must_reveal_played_card_rounds > 0
    )
    npc_must_reveal = (
        game_state.npc.must_reveal_played_card
        or game_state.npc.must_reveal_played_card_rounds > 0
    )

    if player_must_reveal:
        revealed_cards.append(player_card)
        revealed_side = Side.PLAYER
    if npc_must_reveal:
        revealed_cards.append(npc_card)
        revealed_side = Side.NPC if revealed_side is None else None

    return replace(
        game_state,
        player=replace(
            game_state.player,
            must_reveal_played_card=False,
            must_reveal_played_card_rounds=max(
                game_state.player.must_reveal_played_card_rounds - 1, 0
            ),
        ),
        npc=replace(
            game_state.npc,
            must_reveal_played_card=False,
            must_reveal_played_card_rounds=max(
                game_state.npc.must_reveal_played_card_rounds - 1, 0
            ),
        ),
        revealed_this_round=revealed_cards or None,
        revealed_this_round_side=revealed_side,
    )


def _coerce_wildcard_janken(janken: Janken | str | None, side: Side) -> Janken:
    if janken is None:
        return Janken.ROCK
    if isinstance(janken, str):
        janken = Janken(janken)
    if janken not in WILDCARD_DECLARABLE_JANKENS:
        raise ValueError(
            f"{side.value} wildcard declaration must be rock/scissors/paper"
        )
    return janken


def _apply_wildcard_declarations(
    game_state: GameState,
    player_card: Card,
    npc_card: Card,
    *,
    player_wildcard_janken: Janken | str | None,
    npc_wildcard_janken: Janken | str | None,
) -> GameState:
    declarations = (
        (Side.PLAYER, player_card, player_wildcard_janken, "あなた"),
        (Side.NPC, npc_card, npc_wildcard_janken, "NPC"),
    )
    logs: list[str] = []
    for side, card, declared_janken, side_name in declarations:
        if card.janken != Janken.WILDCARD:
            continue
        janken = _coerce_wildcard_janken(declared_janken, side)
        game_state = set_battle_janken_override(game_state, side, janken, card=card)
        logs.append(
            f"R{game_state.round_number}: {side_name}の{card.name}は"
            f"{JANKEN_NAMES[janken]}として扱う"
        )

    if not logs:
        return game_state
    return replace(game_state, battle_log=game_state.battle_log + logs)


def _choose_npc_wildcard_janken(
    game_state: GameState, npc_card: Card, npc_strategy: NpcStrategy
) -> Janken | None:
    if npc_card.janken != Janken.WILDCARD:
        return None

    choose_effect = getattr(npc_strategy, "choose_effect", None)
    if choose_effect is None:
        return random.choice(WILDCARD_DECLARABLE_JANKENS)

    choices = [janken.value for janken in WILDCARD_DECLARABLE_JANKENS]
    return _coerce_wildcard_janken(choose_effect(choices, game_state), Side.NPC)


def init_game(deck: list[Card]) -> GameState:
    """デッキをシャッフルし、手札5枚を配布した GameState を返す。"""
    p_deck = list(deck)
    n_deck = list(deck)
    random.shuffle(p_deck)
    random.shuffle(n_deck)

    p_hand = p_deck[:5]
    p_deck = p_deck[5:]

    n_hand = n_deck[:5]
    n_deck = n_deck[5:]

    return GameState(
        player=PlayerState(hand=p_hand, deck=p_deck),
        npc=PlayerState(hand=n_hand, deck=n_deck),
    )


def start_game(deck: list[Card]) -> GameState:
    state = init_game(deck)
    return replace(state, phase=Phase.SELECT)


def _is_playable_under_constraints(player_state: PlayerState, card: Card) -> bool:
    if card.id in player_state.banned_card_ids:
        return False
    has_forced_card_in_hand = player_state.forced_card_id is not None and any(
        hand_card.id == player_state.forced_card_id for hand_card in player_state.hand
    )
    if has_forced_card_in_hand and card.id != player_state.forced_card_id:
        return False
    return True


def _selectable_cards_under_constraints(player_state: PlayerState) -> list[Card]:
    return [
        card
        for card in player_state.hand
        if _is_playable_under_constraints(player_state, card)
    ]


def _validate_selected_card(player_state: PlayerState, card: Card, side: Side) -> None:
    if all(card.id != hand_card.id for hand_card in player_state.hand):
        raise ValueError(f"{side.value} selected card is not in hand: {card.id}")

    if not _is_playable_under_constraints(player_state, card):
        if (
            player_state.forced_card_id is not None
            and card.id != player_state.forced_card_id
        ):
            raise ValueError(
                f"{side.value} must play forced card: {player_state.forced_card_id}"
            )
        raise ValueError(f"{side.value} cannot play banned card: {card.id}")


def _select_npc_card_with_constraints(
    game_state: GameState, npc_strategy: NpcStrategy
) -> Card:
    constrained_hand = _selectable_cards_under_constraints(game_state.npc)
    if not constrained_hand:
        raise ValueError("npc has no playable cards under current constraints")
    return npc_strategy.select_card(constrained_hand, game_state)


def select_card(
    game_state: GameState,
    player_card: Card,
    npc_strategy: NpcStrategy,
    *,
    wildcard_janken: Janken | str | None = None,
) -> GameState:
    _validate_selected_card(game_state.player, player_card, Side.PLAYER)
    npc_card = _select_npc_card_with_constraints(game_state, npc_strategy)
    npc_wildcard_janken = _choose_npc_wildcard_janken(
        game_state, npc_card, npc_strategy
    )
    return resolve_npc_pending_effects(
        resolve_round(
            game_state,
            player_card,
            npc_card,
            player_wildcard_janken=wildcard_janken,
            npc_wildcard_janken=npc_wildcard_janken,
        ),
        npc_strategy,
    )


def select_card_stepwise(
    game_state: GameState,
    player_card: Card,
    npc_strategy: NpcStrategy,
    *,
    wildcard_janken: Janken | str | None = None,
) -> GameState:
    _validate_selected_card(game_state.player, player_card, Side.PLAYER)
    npc_card = _select_npc_card_with_constraints(game_state, npc_strategy)
    npc_wildcard_janken = _choose_npc_wildcard_janken(
        game_state, npc_card, npc_strategy
    )
    return resolve_round_stepwise(
        game_state,
        player_card,
        npc_card,
        player_wildcard_janken=wildcard_janken,
        npc_wildcard_janken=npc_wildcard_janken,
    )


def resolve_round(
    game_state: GameState,
    player_card: Card,
    npc_card: Card,
    *,
    player_wildcard_janken: Janken | str | None = None,
    npc_wildcard_janken: Janken | str | None = None,
) -> GameState:
    game_state = set_battle_cards_as_played(game_state, player_card, npc_card)
    game_state = apply_must_reveal_played_card(game_state, player_card, npc_card)
    game_state = _apply_wildcard_declarations(
        game_state,
        player_card,
        npc_card,
        player_wildcard_janken=player_wildcard_janken,
        npc_wildcard_janken=npc_wildcard_janken,
    )
    j_res = judge_effective_janken(game_state, player_card, npc_card)

    player_point = None
    npc_point = None
    outcome = None
    winning_side = None

    if j_res == JankenResult.WIN:
        outcome = RoundOutcome.WIN
        winning_side = Side.PLAYER
    elif j_res == JankenResult.LOSE:
        outcome = RoundOutcome.LOSE
        winning_side = Side.NPC
    else:
        outcome = RoundOutcome.EVEN
        winning_side = None

    result = BattleResult(
        outcome=outcome,
        winning_side=winning_side,
        player_card=player_card,
        npc_card=npc_card,
        janken_result=j_res,
        player_point=player_point,
        npc_point=npc_point,
    )

    prefix = f"R{game_state.round_number}:"

    # あいこの場合は効果解決へ、勝負がついた場合は即座に結果反映へ
    if j_res == JankenResult.DRAW:
        p_score = calculate_final_score(game_state.player)
        n_score = calculate_final_score(game_state.npc)
        score_str = f"R{game_state.round_number} [あなた {p_score}pt / NPC {n_score}pt]"

        p_icon = JANKEN_ICONS.get(
            get_effective_janken(game_state, Side.PLAYER, player_card), ""
        )
        n_icon = JANKEN_ICONS.get(
            get_effective_janken(game_state, Side.NPC, npc_card), ""
        )
        log_msg = f"{prefix} あなた({player_card.name}{p_icon}) vs NPC({npc_card.name}{n_icon}) -> じゃんけんあいこ！効果解決へ... {score_str}"
        new_state = replace(
            game_state,
            current_battle=result,
            battle_log=game_state.battle_log + [log_msg],
        )
        new_state = init_effect_resolution(new_state, player_card, npc_card)
        new_state = process_next_effect(new_state)

        # If process_next_effect returns and phase is still EFFECT_RESOLUTION, it means effects are done and points compared.
        # But wait! process_next_effect already handles post-effect point resolution, and leaves the state with the updated current_battle!
        # Actually process_next_effect doesn't call apply_battle_result. We need to call it if effects are done.
        return finalize_round_if_ready(new_state)

    else:
        new_state = apply_battle_result(game_state, result)
        p_score = calculate_final_score(new_state.player)
        n_score = calculate_final_score(new_state.npc)
        score_str = f"R{new_state.round_number} [あなた {p_score}pt / NPC {n_score}pt]"

        p_icon = JANKEN_ICONS.get(
            get_effective_janken(game_state, Side.PLAYER, player_card), ""
        )
        n_icon = JANKEN_ICONS.get(
            get_effective_janken(game_state, Side.NPC, npc_card), ""
        )
        log_msg = f"{prefix} あなた({player_card.name}{p_icon}) vs NPC({npc_card.name}{n_icon}) -> "
        if outcome == RoundOutcome.WIN:
            log_msg += f"あなたの勝ち！ {score_str}"
        elif outcome == RoundOutcome.LOSE:
            log_msg += f"NPCの勝ち！ {score_str}"

        return replace(
            new_state, phase=Phase.REVEAL, battle_log=game_state.battle_log + [log_msg]
        )


def resolve_round_stepwise(
    game_state: GameState,
    player_card: Card,
    npc_card: Card,
    *,
    player_wildcard_janken: Janken | str | None = None,
    npc_wildcard_janken: Janken | str | None = None,
) -> GameState:
    game_state = set_battle_cards_as_played(game_state, player_card, npc_card)
    game_state = apply_must_reveal_played_card(game_state, player_card, npc_card)
    game_state = _apply_wildcard_declarations(
        game_state,
        player_card,
        npc_card,
        player_wildcard_janken=player_wildcard_janken,
        npc_wildcard_janken=npc_wildcard_janken,
    )
    j_res = judge_effective_janken(game_state, player_card, npc_card)

    player_point = None
    npc_point = None
    outcome = None
    winning_side = None

    if j_res == JankenResult.WIN:
        outcome = RoundOutcome.WIN
        winning_side = Side.PLAYER
    elif j_res == JankenResult.LOSE:
        outcome = RoundOutcome.LOSE
        winning_side = Side.NPC
    else:
        outcome = RoundOutcome.EVEN
        winning_side = None

    result = BattleResult(
        outcome=outcome,
        winning_side=winning_side,
        player_card=player_card,
        npc_card=npc_card,
        janken_result=j_res,
        player_point=player_point,
        npc_point=npc_point,
    )

    prefix = f"R{game_state.round_number}:"
    p_icon = JANKEN_ICONS.get(
        get_effective_janken(game_state, Side.PLAYER, player_card), ""
    )
    n_icon = JANKEN_ICONS.get(get_effective_janken(game_state, Side.NPC, npc_card), "")

    if j_res == JankenResult.DRAW:
        p_score = calculate_final_score(game_state.player)
        n_score = calculate_final_score(game_state.npc)
        score_str = f"R{game_state.round_number} [あなた {p_score}pt / NPC {n_score}pt]"
        log_msg = f"{prefix} あなた({player_card.name}{p_icon}) vs NPC({npc_card.name}{n_icon}) -> じゃんけんあいこ！効果解決へ... {score_str}"
        new_state = replace(
            game_state,
            current_battle=result,
            battle_log=game_state.battle_log + [log_msg],
        )
        return init_effect_resolution(new_state, player_card, npc_card)

    new_state = apply_battle_result(game_state, result)
    p_score = calculate_final_score(new_state.player)
    n_score = calculate_final_score(new_state.npc)
    score_str = f"R{new_state.round_number} [あなた {p_score}pt / NPC {n_score}pt]"
    log_msg = f"{prefix} あなた({player_card.name}{p_icon}) vs NPC({npc_card.name}{n_icon}) -> "
    if outcome == RoundOutcome.WIN:
        log_msg += f"あなたの勝ち！ {score_str}"
    elif outcome == RoundOutcome.LOSE:
        log_msg += f"NPCの勝ち！ {score_str}"

    return replace(
        new_state, phase=Phase.REVEAL, battle_log=game_state.battle_log + [log_msg]
    )


def finalize_round_if_ready(state: GameState) -> GameState:
    if state.phase in (Phase.INTERACTIVE_EFFECT, Phase.SELECT):
        return state
    if state.phase == Phase.EFFECT_RESOLUTION and state.effect_queue:
        return state

    # If we are here, effects are fully resolved and current_battle has the final point outcome.
    # We must call apply_battle_result.
    res = state.current_battle
    # But wait, if removal_activated is True, we already consumed the round and cards were discarded/decked in the effect handler!
    # So we don't apply_battle_result if removal was activated!
    if state.removal_activated:
        # Just proceed to REVEAL phase
        return replace(state, phase=Phase.REVEAL)

    final_state = apply_battle_result(state, res)

    p_score = calculate_final_score(final_state.player)
    n_score = calculate_final_score(final_state.npc)
    score_str = f"R{final_state.round_number} [あなた {p_score}pt / NPC {n_score}pt]"

    new_log = list(final_state.battle_log)
    if new_log:
        new_log[-1] = f"{new_log[-1]} {score_str}"

    return replace(final_state, phase=Phase.REVEAL, battle_log=new_log)


def resume_round_effect(game_state: GameState, choice: str | None = None) -> GameState:
    return finalize_round_if_ready(resume_effect(game_state, choice))


def continue_round_effect_step(game_state: GameState) -> GameState:
    return finalize_round_if_ready(process_next_effect_step(game_state))


def resume_round_effect_stepwise(
    game_state: GameState, choice: str | None = None
) -> GameState:
    return finalize_round_if_ready(resume_effect_step(game_state, choice))


def _find_card_by_id(state: GameState, card_id: str) -> Card | None:
    card_lists = [
        [state.current_battle.player_card, state.current_battle.npc_card]
        if state.current_battle
        else [],
        state.player.hand,
        state.player.deck,
        state.player.discard,
        state.player.won_cards,
        state.player.draw_stock,
        state.npc.hand,
        state.npc.deck,
        state.npc.discard,
        state.npc.won_cards,
        state.npc.draw_stock,
    ]
    return next(
        (card for cards in card_lists for card in cards if card.id == card_id), None
    )


def _select_npc_card_ids(
    candidates: list[Card],
    count: int,
    state: GameState,
    npc_strategy: NpcStrategy,
) -> list[str]:
    selected: list[Card] = []
    remaining = list(candidates)
    while remaining and len(selected) < count:
        target = npc_strategy.select_target(remaining, state)
        selected.append(target)
        remaining = [card for card in remaining if card.id != target.id]
    return [card.id for card in selected]


def _choose_npc_pending_effect(
    state: GameState, npc_strategy: NpcStrategy
) -> str | None:
    ctx = state.pending_effect_context
    if ctx is None or ctx.side != Side.NPC:
        return None

    npc = get_player_state(state, Side.NPC)
    source_card = _find_card_by_id(state, ctx.card_id)

    if ctx.effect == "choose":
        variant = ctx.payload.get("choose_variant")
        if ctx.step == 1:
            return_count = int(ctx.payload.get("return_count", 0))
            return ",".join(
                _select_npc_card_ids(npc.hand, return_count, state, npc_strategy)
            )
        if variant == "yuriko_choose":
            return npc_strategy.choose_effect(["gain_points", "draw_cards"], state)
        if variant == "karen_choose":
            if source_card and npc_strategy.should_activate(source_card, state):
                return "activate"
            return "skip"
        return None

    if ctx.effect == "copy_hand":
        candidates = [
            card
            for card in npc.hand
            if card.effect and get_effect_handler(card.effect.type.value)
        ]
        if not candidates:
            candidates = list(npc.hand)
        if not candidates:
            return None
        return npc_strategy.select_target(candidates, state).id

    if ctx.effect == "search_and_swap":
        if not npc.hand or not npc.deck:
            return None
        if npc_strategy.choose_effect(["swap", "skip"], state) == "skip":
            return None
        hand_card = npc_strategy.select_target(npc.hand, state)
        deck_card = npc_strategy.select_target(npc.deck, state)
        return f"{hand_card.id}:{deck_card.id}"

    if ctx.effect == "swap":
        if not npc.hand:
            return None
        if npc_strategy.choose_effect(["swap", "skip"], state) == "skip":
            return None
        return npc_strategy.select_target(npc.hand, state).id

    if ctx.effect == "tutor_play":
        if not source_card or not npc_strategy.should_activate(source_card, state):
            return "skip"
        battle_card = state.current_battle.npc_card if state.current_battle else None
        candidates = list(npc.deck)
        if battle_card is not None:
            candidates.append(battle_card)
        return npc_strategy.select_target(candidates, state).id

    if ctx.effect == "swap_opponent":
        player = get_player_state(state, Side.PLAYER)
        if not player.hand:
            return None
        if npc_strategy.choose_effect(["swap", "skip"], state) == "skip":
            return None
        return "swap"

    if ctx.effect == "removal":
        if source_card and npc_strategy.should_activate(source_card, state):
            return "activate"
        return "skip"

    if ctx.effect == "set_point_match":
        if source_card and npc_strategy.should_activate(source_card, state):
            return "activate"
        return "skip"

    if ctx.effect == "salvage":
        if not npc.discard:
            return None
        if source_card and not npc_strategy.should_activate(source_card, state):
            return None
        return npc_strategy.select_target(npc.discard, state).id

    if ctx.effect == "reorder":
        shuffled = list(npc.deck)
        random.shuffle(shuffled)
        return ",".join(card.id for card in shuffled)

    if ctx.effect == "choose_multiple":
        choices: list[str] = []
        if npc.hand:
            choices.append("discard_buff")
        if npc.deck:
            choices.append("draw_debuff")
        return ",".join(choices) if choices else None

    if ctx.effect == "debuff_counterable":
        if not npc.hand:
            return "skip"
        if (
            source_card
            and npc_strategy.choose_effect(["counter", "skip"], state) == "counter"
        ):
            return npc_strategy.select_target(npc.hand, state).id
        return "skip"

    return None


def resolve_npc_pending_effects(
    game_state: GameState, npc_strategy: NpcStrategy
) -> GameState:
    state = game_state
    while (
        state.phase == Phase.INTERACTIVE_EFFECT
        and state.pending_effect_context
        and state.pending_effect_context.side == Side.NPC
    ):
        choice = _choose_npc_pending_effect(state, npc_strategy)
        state = resume_round_effect(state, choice)
    return state


def resolve_npc_pending_effects_stepwise(
    game_state: GameState, npc_strategy: NpcStrategy
) -> GameState:
    state = game_state
    while (
        state.phase == Phase.INTERACTIVE_EFFECT
        and state.pending_effect_context
        and state.pending_effect_context.side == Side.NPC
    ):
        choice = _choose_npc_pending_effect(state, npc_strategy)
        state = resume_round_effect_stepwise(state, choice)
    return state


def proceed_to_next(game_state: GameState) -> GameState:
    game_state = reset_round_state(game_state)

    if game_state.round_number >= 4:
        return replace(game_state, phase=Phase.RESULT)

    if not game_state.player.hand and not game_state.npc.hand:
        return replace(game_state, phase=Phase.RESULT)

    next_round = game_state.round_number + 1

    while next_round <= 4:
        round_state = replace(game_state, round_number=next_round)
        round_state = apply_next_round_carryover_effects(round_state)

        if not round_state.player.hand and not round_state.npc.hand:
            return replace(round_state, phase=Phase.RESULT)

        forfeit_side = check_forfeit(round_state.player, round_state.npc)
        if forfeit_side is None:
            return replace(round_state, phase=Phase.SELECT)

        game_state = apply_forfeit(round_state, forfeit_side)
        game_state = replace(
            game_state,
            battle_log=game_state.battle_log
            + [format_forfeit_log(next_round, forfeit_side)],
        )
        next_round += 1

    return replace(game_state, phase=Phase.RESULT)
