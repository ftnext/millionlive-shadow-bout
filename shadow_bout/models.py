from dataclasses import dataclass, field
from enum import Enum


class Janken(Enum):
    ROCK = "rock"
    SCISSORS = "scissors"
    PAPER = "paper"
    WILDCARD = "wildcard"


class Phase(Enum):
    START = "start"
    SELECT = "select"
    REVEAL = "reveal"
    RESULT = "result"


class JankenResult(Enum):
    """じゃんけんの三すくみ判定結果（judge_janken の戻り値）"""

    WIN = "win"
    LOSE = "lose"
    DRAW = "draw"  # あいこ → ポイント比較に進む


class RoundOutcome(Enum):
    """1ラウンドの最終結果（BattleResult.outcome の型）"""

    WIN = "win"
    LOSE = "lose"
    EVEN = "even"  # 完全引き分け（あいこストックへ）


class Side(Enum):
    PLAYER = "player"
    NPC = "npc"


@dataclass(frozen=True)
class Card:
    id: str
    name: str
    janken: Janken
    base_point: int


@dataclass(frozen=True)
class PlayerState:
    hand: list[Card] = field(default_factory=list)
    deck: list[Card] = field(default_factory=list)
    discard: list[Card] = field(default_factory=list)
    won_cards: list[Card] = field(default_factory=list)
    draw_stock: list[Card] = field(default_factory=list)


@dataclass(frozen=True)
class BattleResult:
    outcome: RoundOutcome  # WIN / LOSE / EVEN
    winning_side: Side | None  # EVEN の場合は None
    player_card: Card
    npc_card: Card
    janken_result: JankenResult  # じゃんけん段階の結果（WIN/LOSE/DRAW）
    player_point: int | None = None  # あいこ時のみ（ポイント比較した場合）
    npc_point: int | None = None  # あいこ時のみ


@dataclass(frozen=True)
class GameState:
    player: PlayerState
    npc: PlayerState
    round_number: int = 1
    phase: Phase = Phase.START
    battle_log: list[str] = field(default_factory=list)
    current_battle: BattleResult | None = None
