# core/results.py
from dataclasses import dataclass
from typing import Generic, TypeVar, Optional

T = TypeVar("T")


class ResultError(Exception):
    """Raised when unwrap() is called on a failed Result."""


@dataclass(frozen=True)
class Result(Generic[T]):
    success: bool
    value: Optional[T] = None
    error: Optional[str] = None

    @staticmethod
    def ok(value: T) -> "Result[T]":
        return Result(success=True, value=value)

    @staticmethod
    def err(error: str) -> "Result[T]":
        return Result(success=False, error=error)

    def unwrap(self) -> T:
        if not self.success:
            raise ResultError(self.error or "unknown error")
        return self.value  # type: ignore[return-value]
