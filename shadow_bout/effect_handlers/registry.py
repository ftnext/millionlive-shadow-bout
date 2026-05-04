from typing import Callable

from shadow_bout.models import Card, GameState, Side

EffectHandler = Callable[[GameState, Side, Card], GameState]
_registry: dict[str, EffectHandler] = {}


def register(effect_type: str):
    def decorator(fn: EffectHandler):
        _registry[effect_type] = fn
        return fn

    return decorator


def get_effect_handler(effect_type: str) -> EffectHandler | None:
    return _registry.get(effect_type)
