import random
from dataclasses import replace

from shadow_bout.effects import init_effect_resolution, process_next_effect
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


def judge_janken(card_a: Card, card_b: Card) -> JankenResult:
    """じゃんけんの三すくみ判定のみ。WIN / LOSE / DRAW を返す。"""
    a = card_a.janken
    b = card_b.janken

    if a == b:
        return JankenResult.DRAW

    win_map = {
        Janken.ROCK: Janken.SCISSORS,
        Janken.SCISSORS: Janken.PAPER,
        Janken.PAPER: Janken.ROCK,
    }

    if win_map[a] == b:
        return JankenResult.WIN
    else:
        return JankenResult.LOSE


def compare_points(card_a: Card, card_b: Card) -> RoundOutcome:
    pass  # Replaced by calculate_effective_point in effects.py


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
        # プレイヤー不戦敗: NPCが山札から1枚めくり、それがNPCの勝ち札になる
        if npc.deck:
            card = npc.deck[0]
            new_n_deck = npc.deck[1:]
            new_n_won = list(npc.won_cards) + [card]
            new_npc = replace(npc, deck=new_n_deck, won_cards=new_n_won)
        else:
            new_npc = npc

        # プレイヤーは手札がないので何もしない（本当は場に出そうとしたカードがあるはずだが不戦敗時はスキップされる想定）
        return replace(game_state, npc=new_npc)

    else:
        # NPC不戦敗
        if player.deck:
            card = player.deck[0]
            new_p_deck = player.deck[1:]
            new_p_won = list(player.won_cards) + [card]
            new_player = replace(player, deck=new_p_deck, won_cards=new_p_won)
        else:
            new_player = player

        return replace(game_state, player=new_player)


def calculate_final_score(state: PlayerState) -> int:
    """勝ち札の base_point 合計"""
    return sum(card.base_point for card in state.won_cards)


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


def select_card(
    game_state: GameState, player_card: Card, npc_strategy: NpcStrategy
) -> GameState:
    npc_card = npc_strategy.select_card(game_state.npc.hand, game_state)
    return resolve_round(game_state, player_card, npc_card)


def resolve_round(
    game_state: GameState, player_card: Card, npc_card: Card
) -> GameState:
    j_res = judge_janken(player_card, npc_card)

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

        p_icon = JANKEN_ICONS.get(player_card.janken, "")
        n_icon = JANKEN_ICONS.get(npc_card.janken, "")
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

        p_icon = JANKEN_ICONS.get(player_card.janken, "")
        n_icon = JANKEN_ICONS.get(npc_card.janken, "")
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


def proceed_to_next(game_state: GameState) -> GameState:
    if game_state.round_number >= 4:
        return replace(game_state, phase=Phase.RESULT)

    next_round = game_state.round_number + 1

    # 不戦敗チェック
    forfeit_side = check_forfeit(game_state.player, game_state.npc)
    if forfeit_side:
        game_state = apply_forfeit(game_state, forfeit_side)
        # 不戦敗が発生してもラウンドは進む？それとも即終了？
        # 一般的なゲームなら即終了か、そのラウンドを落とす。
        # ここでは不戦敗処理をしてからRESULTへ
        return replace(game_state, phase=Phase.RESULT)

    return replace(
        game_state, round_number=next_round, phase=Phase.SELECT, current_battle=None
    )
