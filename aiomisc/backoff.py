import asyncio
from functools import wraps
from typing import Callable, Optional, Type, TypeVar, Union

from .timeout import timeout


Number = Union[int, float]
T = TypeVar('T')


# noinspection SpellCheckingInspection
def asyncbackoff(attempt_timeout: Optional[Number],
                 deadline: Optional[Number],
                 pause: Number = 0,
                 *exc: Type[Exception], exceptions=(),
                 max_tries: int = None,
                 giveup: Callable[[Exception], bool] = None):

    exceptions = exc + tuple(exceptions)

    if not pause:
        pause = 0
    elif pause < 0:
        raise ValueError("'pause' must be positive")

    if attempt_timeout is not None and attempt_timeout < 0:
        raise ValueError("'attempt_timeout' must be positive or None")

    if deadline is not None and deadline < 0:
        raise ValueError("'deadline' must be positive or None")

    if max_tries is not None and max_tries < 1:
        raise ValueError("'max_retries' must be >= 1 or None")

    if giveup is not None and not callable(giveup):
        raise ValueError("'giveup' must be a callable or None")

    exceptions = tuple(exceptions) or ()
    exceptions += asyncio.TimeoutError,

    def decorator(func):
        if attempt_timeout is not None:
            func = timeout(attempt_timeout)(func)

        @wraps(func)
        async def wrap(*args, **kwargs):
            loop = asyncio.get_event_loop()
            last_exc = None
            tries = 0

            async def run():
                nonlocal last_exc, tries

                while True:
                    tries += 1
                    try:
                        return await asyncio.wait_for(
                            func(*args, **kwargs),
                            loop=loop,
                            timeout=attempt_timeout
                        )
                    except asyncio.CancelledError:
                        raise
                    except exceptions as e:
                        last_exc = e
                        if max_tries is not None and tries >= max_tries:
                            raise
                        if giveup and giveup(e):
                            raise
                        await asyncio.sleep(pause, loop=loop)

            try:
                return await asyncio.wait_for(
                    run(), timeout=deadline, loop=loop
                )
            except Exception:
                if last_exc:
                    raise last_exc
                raise

        return wrap
    return decorator
