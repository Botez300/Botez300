# Backtesting framework (`legion/backtest/`)

## What it guarantees
- **No look-ahead:** each decision at bar i uses only bars 0..i (tested).
- **Orders execute on bar i+1.**
- **Conservative fills:** adverse slippage and half-spread both ways; no fill if the trigger bar opens above the permitted range; gap-through-stop fills at the open; stop assumed before target on ambiguous bars.
- **Exits on the final bar are processed.** A defect where they were skipped was found and fixed this phase.
- **Experiment tools:** walk-forward that selects on TRAIN only and trades only out-of-sample; parameter sensitivity; an exit-variant grid (`exits.variants()`, 2 stops x targets x trails x {5, 10, 20} sessions).
- **Metrics:** total return, CAGR, win rate, expectancy (R), profit factor, per-trade Sharpe/Sortino, max drawdown, recovery factor, average win/loss, hold, MFE/MAE, consecutive losses, costs, exit reasons.

## What is BLOCKED (not run)
- **1/3/5/10-year stock backtests:** need a point-in-time IWM/US universe including delisted names, plus bulk OHLCV pulls on the host. Without them, results carry survivorship bias (`BIAS_DISCLOSURE`).
- **Options backtests:** need historical options data (Robinhood exposes current chains only).
- **Regime segmentation:** implemented hook (`regime` map); needs SPY/QQQ/IWM history.
- **Benchmark comparison against SPY and cash:** needs the same history.

## Only real-data run
A smoke test on INSM 2026-09-01..11-25 (61 bars) found **0 setups and 0 trades**. That is correct: the only anchor is the last candle. It says nothing about profitability.
