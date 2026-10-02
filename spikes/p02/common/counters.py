"""Callback invocation counters (specification §3.3).

A call is one invocation of the block's Python value or Jacobian method, whatever the backend's
batch size. Nothing else counts.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BlockCounters:
    """Counters for one callback block."""

    name: str
    value_calls: int = 0
    jacobian_calls: int = 0

    def record_value(self) -> None:
        self.value_calls += 1

    def record_jacobian(self) -> None:
        self.jacobian_calls += 1

    def snapshot(self) -> dict[str, int]:
        return {"value_calls": self.value_calls, "jacobian_calls": self.jacobian_calls}

    def reset(self) -> None:
        self.value_calls = 0
        self.jacobian_calls = 0


@dataclass
class CounterSet:
    """The counters of every block in a harness."""

    blocks: dict[str, BlockCounters] = field(default_factory=dict)

    def block(self, name: str) -> BlockCounters:
        if name not in self.blocks:
            self.blocks[name] = BlockCounters(name)
        return self.blocks[name]

    def snapshot(self) -> dict[str, dict[str, int]]:
        return {name: counter.snapshot() for name, counter in self.blocks.items()}

    def reset(self) -> None:
        for counter in self.blocks.values():
            counter.reset()
