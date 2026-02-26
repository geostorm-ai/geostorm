"""Repository layer — all SQL lives here."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractAsyncContextManager

    import aiosqlite

    GetConnection: TypeAlias = Callable[[], AbstractAsyncContextManager[aiosqlite.Connection]]
