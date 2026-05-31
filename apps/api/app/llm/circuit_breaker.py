"""Per-request cost circuit breaker (FR-GN-5, architecture §2.5).

``guard()`` computes projected cost from input token count and the worst-case
output (``max_output_tokens``) and raises ``CostCeilingExceeded`` before any
LLM call is made.

Author: Al Amin Ahamed.
"""

from __future__ import annotations


class CostCeilingExceeded(Exception):  # noqa: N818
    """Raised when a projected request cost exceeds the configured ceiling.

    Attributes:
        projected_cost: Estimated cost in USD.
        ceiling: Configured ceiling in USD.
    """

    def __init__(self, *, projected_cost: float, ceiling: float) -> None:
        """Initialize the exception with projected cost and ceiling.

        Args:
            projected_cost: Estimated cost in USD.
            ceiling: Configured ceiling in USD.
        """
        self.projected_cost = projected_cost
        self.ceiling = ceiling
        super().__init__(
            f"projected_cost={projected_cost:.4f} USD exceeds ceiling={ceiling:.4f} USD"
        )


def guard(
    input_tokens: int,
    *,
    cost_per_1k_input: float,
    cost_per_1k_output: float,
    max_output_tokens: int,
    ceiling: float,
) -> None:
    """Refuse a request whose projected cost exceeds the ceiling.

    The projected cost is a worst-case estimate: actual input tokens plus the
    configured maximum output token count.

    Args:
        input_tokens: Number of input tokens in the prompt.
        cost_per_1k_input: Cost per 1 000 input tokens in USD.
        cost_per_1k_output: Cost per 1 000 output tokens in USD.
        max_output_tokens: Maximum output tokens configured for this call.
        ceiling: Per-request cost ceiling in USD.

    Raises:
        CostCeilingExceeded: If ``projected_cost >= ceiling``.
    """
    projected = (input_tokens / 1000.0) * cost_per_1k_input + (
        max_output_tokens / 1000.0
    ) * cost_per_1k_output
    if projected >= ceiling:
        raise CostCeilingExceeded(projected_cost=projected, ceiling=ceiling)
