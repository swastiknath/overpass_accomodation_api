"""Daily budget and token guard for LLM calls."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from config import Settings, load_settings

logger = logging.getLogger("llm.budget")


class BudgetGuard:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or load_settings()
        self.current_day: str = datetime.now(timezone.utc).date().isoformat()
        self.tokens_used_today: int = 0
        self.cost_usd_today: float = 0.0

    def _rollover_if_new_day(self):
        today = datetime.now(timezone.utc).date().isoformat()
        if today != self.current_day:
            self.current_day = today
            self.tokens_used_today = 0
            self.cost_usd_today = 0.0

    def can_make_request(self) -> bool:
        self._rollover_if_new_day()
        if self.tokens_used_today >= self.settings.llm_daily_token_limit:
            logger.warning(
                f"Daily token limit reached: {self.tokens_used_today} / {self.settings.llm_daily_token_limit}"
            )
            return False
        if self.cost_usd_today >= self.settings.llm_daily_budget_usd:
            logger.warning(
                f"Daily USD budget reached: ${self.cost_usd_today:.2f} / ${self.settings.llm_daily_budget_usd:.2f}"
            )
            return False
        return True

    def record_usage(self, prompt_tokens: int, completion_tokens: int, estimated_cost_usd: float = 0.001):
        self._rollover_if_new_day()
        total_tokens = prompt_tokens + completion_tokens
        self.tokens_used_today += total_tokens
        self.cost_usd_today += estimated_cost_usd
        logger.info(
            f"LLM usage recorded: {total_tokens} tokens (${estimated_cost_usd:.4f}). "
            f"Daily total: {self.tokens_used_today} tokens (${self.cost_usd_today:.4f})"
        )


GLOBAL_BUDGET = BudgetGuard()
