# Import modules for their @register side effects.
from shadow_bout.effect_handlers import cards as _cards  # noqa: F401
from shadow_bout.effect_handlers import interactive as _interactive  # noqa: F401
from shadow_bout.effect_handlers import points as _points  # noqa: F401
from shadow_bout.effect_handlers.registry import (
    EffectHandler,
    get_effect_handler,
    register,
)
from shadow_bout.effect_handlers.resume import resume_pending_effect

__all__ = [
    "EffectHandler",
    "get_effect_handler",
    "register",
    "resume_pending_effect",
]
