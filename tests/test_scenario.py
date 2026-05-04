import json
import random
from pathlib import Path

import pytest

from shadow_bout.engine import init_game_with_required, start_game_with_scenario
from shadow_bout.models import Card, GameState, Janken, PlayerState
from shadow_bout.npc import RandomStrategy, ScriptedStrategy
from shadow_bout.scenario import Scenario, ScenarioRound, load_scenario

DECK_IDS = [f"card_{i:02d}" for i in range(1, 14)]


def _build_card(card_id: str) -> Card:
    return Card(card_id, card_id, "kana", Janken.ROCK, 10)


def _build_deck() -> list[Card]:
    return [_build_card(card_id) for card_id in DECK_IDS]


def _write_scenario(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "dev_scenario.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_load_scenario_full(tmp_path):
    path = _write_scenario(
        tmp_path,
        {
            "player_hand": ["card_01", "card_02"],
            "npc_hand": ["card_03"],
            "rounds": [
                {"player_card": "card_01"},
                None,
                {"npc_card": "card_03", "npc_wildcard": "rock"},
                {"player_card": "card_02", "player_wildcard": "scissors"},
            ],
        },
    )

    scenario = load_scenario(path, deck_card_ids=DECK_IDS)

    assert scenario.player_hand_required == ("card_01", "card_02")
    assert scenario.npc_hand_required == ("card_03",)
    assert len(scenario.rounds) == 4
    assert scenario.rounds[0] == ScenarioRound(player_card_id="card_01")
    assert scenario.rounds[1] is None
    assert scenario.rounds[2] == ScenarioRound(
        npc_card_id="card_03", npc_wildcard=Janken.ROCK
    )
    assert scenario.rounds[3] == ScenarioRound(
        player_card_id="card_02", player_wildcard=Janken.SCISSORS
    )


def test_load_scenario_minimal(tmp_path):
    path = _write_scenario(tmp_path, {})
    scenario = load_scenario(path, deck_card_ids=DECK_IDS)
    assert scenario == Scenario()


def test_load_scenario_partial_rounds(tmp_path):
    path = _write_scenario(tmp_path, {"rounds": [{"player_card": "card_05"}]})
    scenario = load_scenario(path, deck_card_ids=DECK_IDS)
    assert len(scenario.rounds) == 1
    assert scenario.rounds[0].player_card_id == "card_05"


def test_load_scenario_rejects_oversized_hand(tmp_path):
    path = _write_scenario(
        tmp_path,
        {"player_hand": [f"card_{i:02d}" for i in range(1, 7)]},
    )
    with pytest.raises(ValueError, match="at most 5"):
        load_scenario(path, deck_card_ids=DECK_IDS)


def test_load_scenario_rejects_unknown_card(tmp_path):
    path = _write_scenario(tmp_path, {"player_hand": ["card_99"]})
    with pytest.raises(ValueError, match="unknown card id"):
        load_scenario(path, deck_card_ids=DECK_IDS)


def test_load_scenario_rejects_duplicate_hand(tmp_path):
    path = _write_scenario(tmp_path, {"player_hand": ["card_01", "card_01"]})
    with pytest.raises(ValueError, match="duplicates"):
        load_scenario(path, deck_card_ids=DECK_IDS)


def test_load_scenario_rejects_non_string_hand_entry(tmp_path):
    path = _write_scenario(tmp_path, {"player_hand": [{"id": "card_01"}]})
    with pytest.raises(ValueError, match="must be strings"):
        load_scenario(path, deck_card_ids=DECK_IDS)


def test_load_scenario_rejects_too_many_rounds(tmp_path):
    path = _write_scenario(
        tmp_path,
        {
            "rounds": [
                {"player_card": "card_01"},
                {"player_card": "card_02"},
                {"player_card": "card_03"},
                {"player_card": "card_04"},
                {"player_card": "card_05"},
            ]
        },
    )
    with pytest.raises(ValueError, match="at most 4"):
        load_scenario(path, deck_card_ids=DECK_IDS)


def test_load_scenario_rejects_empty_round_object(tmp_path):
    path = _write_scenario(tmp_path, {"rounds": [{}]})
    with pytest.raises(ValueError, match="empty objects are not allowed"):
        load_scenario(path, deck_card_ids=DECK_IDS)


def test_load_scenario_allows_null_round(tmp_path):
    path = _write_scenario(tmp_path, {"rounds": [None, {"player_card": "card_02"}]})
    scenario = load_scenario(path, deck_card_ids=DECK_IDS)
    assert scenario.rounds[0] is None
    assert scenario.rounds[1].player_card_id == "card_02"


def test_load_scenario_rejects_invalid_wildcard(tmp_path):
    path = _write_scenario(tmp_path, {"rounds": [{"player_wildcard": "wildcard"}]})
    with pytest.raises(ValueError, match="player_wildcard"):
        load_scenario(path, deck_card_ids=DECK_IDS)


def test_load_scenario_rejects_unknown_round_field(tmp_path):
    path = _write_scenario(
        tmp_path, {"rounds": [{"player_card": "card_01", "extra": 1}]}
    )
    with pytest.raises(ValueError, match="unknown keys"):
        load_scenario(path, deck_card_ids=DECK_IDS)


def test_init_game_with_required_places_required_in_hand():
    deck = _build_deck()
    required = ["card_07", "card_13"]
    random.seed(0)
    state = init_game_with_required(deck, player_required_hand=required)
    hand_ids = {card.id for card in state.player.hand}
    assert {"card_07", "card_13"}.issubset(hand_ids)
    assert len(state.player.hand) == 5
    assert len(state.player.deck) == len(deck) - 5
    all_ids = {card.id for card in state.player.hand + state.player.deck}
    assert all_ids == set(DECK_IDS)


def test_init_game_with_required_npc_independent_pool():
    deck = _build_deck()
    state = init_game_with_required(
        deck,
        player_required_hand=["card_01"],
        npc_required_hand=["card_02"],
    )
    assert any(c.id == "card_01" for c in state.player.hand)
    assert any(c.id == "card_02" for c in state.npc.hand)


def test_init_game_with_required_unknown_card_raises():
    deck = _build_deck()
    with pytest.raises(ValueError, match="required card not found"):
        init_game_with_required(deck, player_required_hand=["card_99"])


def test_start_game_with_scenario_sets_select_phase():
    deck = _build_deck()
    scenario = Scenario(
        player_hand_required=("card_01",),
        npc_hand_required=("card_02",),
        rounds=(),
    )
    state = start_game_with_scenario(deck, scenario)
    assert state.phase.value == "select"
    assert any(c.id == "card_01" for c in state.player.hand)
    assert any(c.id == "card_02" for c in state.npc.hand)


def _make_game_state(round_number: int = 1) -> GameState:
    return GameState(player=PlayerState(), npc=PlayerState(), round_number=round_number)


def test_scripted_strategy_select_card_uses_spec():
    cards = [_build_card("card_01"), _build_card("card_02")]
    scenario = Scenario(
        rounds=(ScenarioRound(npc_card_id="card_02"),),
    )
    strategy = ScriptedStrategy(scenario)
    selected = strategy.select_card(cards, _make_game_state(round_number=1))
    assert selected.id == "card_02"


def test_scripted_strategy_select_card_falls_back_when_unspecified():
    cards = [_build_card("card_01")]
    scenario = Scenario(rounds=(None,))
    strategy = ScriptedStrategy(scenario)
    selected = strategy.select_card(cards, _make_game_state(round_number=1))
    assert selected.id == "card_01"


def test_scripted_strategy_select_card_falls_back_when_id_missing_from_hand():
    cards = [_build_card("card_01")]
    scenario = Scenario(
        rounds=(ScenarioRound(npc_card_id="card_99"),),
    )
    strategy = ScriptedStrategy(scenario)
    selected = strategy.select_card(cards, _make_game_state(round_number=1))
    assert selected.id == "card_01"


def test_scripted_strategy_declare_wildcard_uses_spec():
    scenario = Scenario(
        rounds=(ScenarioRound(npc_wildcard=Janken.SCISSORS),),
    )
    strategy = ScriptedStrategy(scenario)
    choices = ["rock", "scissors", "paper"]
    assert (
        strategy.declare_wildcard_janken(choices, _make_game_state(round_number=1))
        == "scissors"
    )


def test_scripted_strategy_declare_wildcard_falls_back_when_unspecified():
    scenario = Scenario(rounds=(None,))
    strategy = ScriptedStrategy(scenario)
    random.seed(0)
    choice = strategy.declare_wildcard_janken(
        ["rock", "scissors", "paper"], _make_game_state(round_number=1)
    )
    assert choice in {"rock", "scissors", "paper"}


def test_scripted_strategy_does_not_override_choose_effect_for_special():
    """美希効果（special）の choose_effect 経路は wildcard 宣言と分離されているため、
    npc_wildcard 指定があっても choose_effect の挙動は Random にフォールバックする。"""
    scenario = Scenario(
        rounds=(ScenarioRound(npc_wildcard=Janken.ROCK),),
    )
    strategy = ScriptedStrategy(scenario)
    random.seed(0)
    chosen = strategy.choose_effect(
        ["rock", "scissors", "paper"], _make_game_state(round_number=1)
    )
    assert chosen in {"rock", "scissors", "paper"}


def test_random_strategy_implements_declare_wildcard_janken():
    strategy = RandomStrategy()
    random.seed(0)
    choice = strategy.declare_wildcard_janken(
        ["rock", "scissors", "paper"], _make_game_state()
    )
    assert choice in {"rock", "scissors", "paper"}
