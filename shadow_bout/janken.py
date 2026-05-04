from shadow_bout.models import Janken, JankenResult


def judge_janken_values(a: Janken, b: Janken) -> JankenResult:
    """じゃんけんの三すくみ判定のみ。WIN / LOSE / DRAW を返す。"""
    if a == b:
        return JankenResult.DRAW

    win_map = {
        Janken.ROCK: Janken.SCISSORS,
        Janken.SCISSORS: Janken.PAPER,
        Janken.PAPER: Janken.ROCK,
    }

    if a not in win_map or b not in win_map:
        return JankenResult.DRAW

    if win_map[a] == b:
        return JankenResult.WIN
    return JankenResult.LOSE
