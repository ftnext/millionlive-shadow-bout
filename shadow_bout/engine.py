import random
from dataclasses import replace

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


def compare_points(
    card_a: Card, hand_size_a: int, card_b: Card, hand_size_b: int
) -> RoundOutcome:
    """あいこ時のポイント比較。base_point + hand_size（場に出した後の手札枚数）で比較"""
    point_a = card_a.base_point + hand_size_a
    point_b = card_b.base_point + hand_size_b

    if point_a > point_b:
        return RoundOutcome.WIN
    elif point_a < point_b:
        return RoundOutcome.LOSE
    else:
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
        new_n_stock = []

        new_p_discard.append(p_card)  # 自分の出したカードは捨て札（勝ち札にならない）
        # ※仕様再確認: 勝者: 相手の場のカード → 自分の勝ち札。自分の場のカード → 自分の捨て札？
        # 勝ち札は「得点になるカード」なので、相手のカードを奪うイメージ
        # 自分の出したカードは役目を終えて捨て札へ。

    elif result.outcome == RoundOutcome.LOSE:
        # NPCの勝ち
        new_n_won.append(p_card)
        new_n_won.extend(new_p_stock)
        new_p_stock = []

        new_n_discard.append(n_card)
        new_p_discard.append(p_card)  # 負けたカードも捨て札

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

    if j_res == JankenResult.WIN:
        outcome = RoundOutcome.WIN
    elif j_res == JankenResult.LOSE:
        outcome = RoundOutcome.LOSE
    else:
        # あいこ
        # 手札枚数は「場に出した後」の残り枚数
        p_hand_size = len(game_state.player.hand) - 1
        n_hand_size = len(game_state.npc.hand) - 1
        player_point = player_card.base_point + p_hand_size
        npc_point = npc_card.base_point + n_hand_size

        outcome = compare_points(player_card, p_hand_size, npc_card, n_hand_size)

    winning_side = None
    if outcome == RoundOutcome.WIN:
        winning_side = Side.PLAYER
    elif outcome == RoundOutcome.LOSE:
        winning_side = Side.NPC

    result = BattleResult(
        outcome=outcome,
        winning_side=winning_side,
        player_card=player_card,
        npc_card=npc_card,
        janken_result=j_res,
        player_point=player_point,
        npc_point=npc_point,
    )

    new_state = apply_battle_result(game_state, result)

    # ログ追加
    log_msg = f"R{game_state.round_number}: あなた({player_card.name}) vs NPC({npc_card.name}) -> "
    if outcome == RoundOutcome.WIN:
        log_msg += "あなたの勝ち！"
    elif outcome == RoundOutcome.LOSE:
        log_msg += "NPCの勝ち！"
    else:
        log_msg += "引き分け！"

    new_battle_log = list(game_state.battle_log)
    new_battle_log.append(log_msg)

    return replace(new_state, phase=Phase.REVEAL, battle_log=new_battle_log)


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
