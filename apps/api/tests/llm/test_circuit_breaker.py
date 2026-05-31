"""Tests for per-request cost circuit breaker (FR-GN-5)."""

from __future__ import annotations

import pytest


def test_guard_passes_within_ceiling() -> None:
    from app.llm.circuit_breaker import guard

    # 1000 input tokens * $0.003/1k + 512 output tokens * $0.015/1k
    # = $0.003 + $0.00768 = $0.01068 — well below $0.10
    guard(
        input_tokens=1000,
        cost_per_1k_input=0.003,
        cost_per_1k_output=0.015,
        max_output_tokens=512,
        ceiling=0.10,
    )  # must not raise


def test_guard_raises_on_projected_overrun() -> None:
    from app.llm.circuit_breaker import CostCeilingExceeded, guard

    # 10000 input * $0.003/1k + 2048 output * $0.015/1k = $0.03 + $0.0307 = $0.0607
    # Ceiling is $0.05 → should raise
    with pytest.raises(CostCeilingExceeded) as exc_info:
        guard(
            input_tokens=10000,
            cost_per_1k_input=0.003,
            cost_per_1k_output=0.015,
            max_output_tokens=2048,
            ceiling=0.05,
        )
    assert exc_info.value.projected_cost > exc_info.value.ceiling


def test_guard_raises_exactly_at_ceiling() -> None:
    from app.llm.circuit_breaker import CostCeilingExceeded, guard

    # Projected = ceiling exactly → should raise (strict >=)
    with pytest.raises(CostCeilingExceeded):
        guard(
            input_tokens=1000,
            cost_per_1k_input=0.10,
            cost_per_1k_output=0.0,
            max_output_tokens=0,
            ceiling=0.10,
        )


def test_cost_ceiling_exceeded_carries_amounts() -> None:
    from app.llm.circuit_breaker import CostCeilingExceeded

    exc = CostCeilingExceeded(projected_cost=0.15, ceiling=0.10)
    assert exc.projected_cost == 0.15
    assert exc.ceiling == 0.10
    assert "0.15" in str(exc)
