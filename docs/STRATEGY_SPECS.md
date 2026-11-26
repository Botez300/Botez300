# Strategy specifications required

**Superseded (Phase 3):** specs are now format 2, derived from `specs/source/legion_scanner_instructions_2026-11-26.md` (hash recorded in every spec). See docs/ASSUMPTIONS_APPROVAL.md and docs/CAPABILITY_GAPS.md. The text below describes the legacy format-1 path, still supported for compatibility.
Each of `specs/*.json` is `status: INCOMPLETE` with every parameter `null`. A strategy is COMPLETE only when its file has
`status: COMPLETE`, `source_document` + `source_sha256`, every parameter non-null, and at least one valid `exit_rules` entry
(`channel_exit`, `ma_break_weeks`, `max_hold_days`, `trailing_pct`). Until then every entry originating from that strategy is blocked
(`STRATEGY_INCOMPLETE`).

Parameters the modules read: CAN_SLIM (breakout_volume_multiple, max_extension_above_pivot_pct, min_eps_growth_pct, min_rs_excess_return_pct);
MINERVINI_VCP_SEPA (sma_stack_periods, sma_long_rising_days, min_pct_above_52w_low, max_pct_below_52w_high, breakout_volume_multiple,
min_rs_excess_return_pct); TURTLE (entry_lookback, atr_period, stop_atr_multiple, exit_lookback); WEINSTEIN_STAGE_2 (ma_weeks, ma_slope_weeks,
breakout_volume_multiple, min_rs_excess_return_pct); MAGIC_FORMULA (max_combined_rank, rebalance_days; needs an external universe ranking);
PARABOLIC_MOMENTUM (momentum_lookback_days, min_return_pct, breakout_volume_multiple, max_extension_from_sma_pct, sma_period).

Known limits even with a COMPLETE spec: CAN SLIM EPS growth cannot be independently verified from Robinhood fundamentals (always UNVERIFIED -> blocks);
Magic Formula needs a ranking job that does not exist yet; VCP contraction pattern itself is not verified (only the trend-template numbers).
No bearish strategy spec exists, so bearish options remain blocked in the live path.
