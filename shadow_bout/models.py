from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Janken(Enum):
    ROCK = "rock"
    SCISSORS = "scissors"
    PAPER = "paper"
    WILDCARD = "wildcard"


class Phase(Enum):
    START = "start"
    SELECT = "select"
    REVEAL = "reveal"
    EFFECT_RESOLUTION = "effect_resolution"
    INTERACTIVE_EFFECT = "interactive_effect"
    RESULT = "result"


class EffectType(Enum):
    BUFF = "buff"
    BUFF_DYNAMIC = "buff_dynamic"
    NEGATE = "negate"
    REVEAL = "reveal"
    REVEAL_ALL = "reveal_all"
    SWAP = "swap"
    COPY_HAND = "copy_hand"
    COPY_EFFECT = "copy_effect"
    RESTART = "restart"
    SEARCH_AND_SWAP = "search_and_swap"
    REMOVAL = "removal"
    CHOOSE = "choose"
    NULL = "null"
    # Other types for full deck compatibility
    DRAW = "draw"
    SPECIAL = "special"
    DEBUFF = "debuff"
    BUFF_NEXT = "buff_next"
    CHANGE_JANKEN = "change_janken"
    SET_POINT = "set_point"
    FORCE_PLAY = "force_play"
    DEBUFF_CONDITIONAL = "debuff_conditional"
    DRAW_DYNAMIC = "draw_dynamic"
    STEAL_DRAW = "steal_draw"
    REORDER = "reorder"
    BUFF_SCALING = "buff_scaling"
    CHOOSE_MULTIPLE = "choose_multiple"
    WIN_CONDITION = "win_condition"
    IMMUNE = "immune"
    DEBUFF_COUNTERABLE = "debuff_counterable"
    SET_POINT_MATCH = "set_point_match"
    DEBUFF_PERSISTENT = "debuff_persistent"
    SWAP_OPPONENT = "swap_opponent"
    CONDITIONAL_NEGATE_BUFF = "conditional_negate_buff"
    BUFF_SNOWBALL = "buff_snowball"
    BUFF_AND_PEEK = "buff_and_peek"
    SALVAGE = "salvage"
    CONDITIONAL_DEBUFF_DRAW = "conditional_debuff_draw"
    CONDITIONAL_BUFF = "conditional_buff"
    STEAL_HAND = "steal_hand"
    CONDITIONAL_DEBUFF_NEXT = "conditional_debuff_next"
    TUTOR_PLAY = "tutor_play"
    WILDCARD = "wildcard"
    CURSE = "curse"
    BAN = "ban"


@dataclass(frozen=True)
class Effect:
    type: EffectType
    description: str
    value: int | float | str | None = None


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
class BattleJankenOverride:
    side: Side
    card_id: str
    janken: Janken


@dataclass(frozen=True)
class Card:
    id: str
    name: str
    kana: str
    janken: Janken
    base_point: int
    effect: Effect | None = None


@dataclass(frozen=True)
class PlayerState:
    hand: list[Card] = field(default_factory=list)
    deck: list[Card] = field(default_factory=list)
    discard: list[Card] = field(default_factory=list)
    won_cards: list[Card] = field(default_factory=list)
    draw_stock: list[Card] = field(default_factory=list)
    revealed_card_ids: frozenset[str] = frozenset()
    point_modifier: int = 0
    conditional_point_modifier_non_wildcard: int = 0
    janken_override: Janken | None = None
    next_round_point_modifier: int = 0
    next_round_conditional_point_modifier_non_wildcard: int = 0
    next_round_janken_override: Janken | None = None
    effect_negated: bool = False
    banned_card_ids: frozenset[str] = frozenset()
    forced_card_id: str | None = None
    must_reveal_played_card: bool = False
    must_reveal_played_card_rounds: int = 0
    persistent_point_effects: tuple["PersistentPointEffect", ...] = ()


@dataclass(frozen=True)
class PersistentPointEffect:
    value: int
    remaining_turns: int


@dataclass(frozen=True)
class PointMatchEffect:
    source_side: Side
    target_side: Side


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
class CompletedRound:
    """1ラウンドの最終的な経過。通常決着なら `battle` に BattleResult、
    不戦敗で進行したラウンドなら `forfeiting_side` がセットされる。"""

    round_number: int
    battle: BattleResult | None = None
    forfeiting_side: Side | None = None


@dataclass(frozen=True)
class PendingEffectContext:
    side: Side
    card_id: str
    effect: str
    step: int = 0
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GameState:
    player: PlayerState
    npc: PlayerState
    round_number: int = 1
    phase: Phase = Phase.START
    battle_log: list[str] = field(default_factory=list)
    current_battle: BattleResult | None = None
    completed_rounds: tuple[CompletedRound, ...] = ()
    last_restart_round: int | None = None
    effect_step: int = 0
    pending_effect_context: PendingEffectContext | None = None
    effect_queue: list[tuple[Side, Card]] = field(default_factory=list)
    removal_activated: bool = False
    revealed_this_round: list[Card] | None = None
    revealed_this_round_side: Side | None = None
    pending_conditional_debuff_on_loss: tuple[tuple[Side, int], ...] = ()
    pending_draw_on_win: tuple[tuple[Side, int], ...] = ()
    pending_next_round_buff_on_win: tuple[tuple[Side, int], ...] = ()
    point_match_effects: tuple[PointMatchEffect, ...] = ()
    battle_janken_overrides: tuple[BattleJankenOverride, ...] = ()
    win_condition_winner: Side | None = None
