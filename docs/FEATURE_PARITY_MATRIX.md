# Feature parity matrix

States: **IMPLEMENTED** (built, tested) · **PARTIAL** · **PLANNED** (milestone) · **BLOCKED** (external dependency) ·
**NOT REPRODUCIBLE** (cannot be rebuilt from public information; an original alternative is planned instead).

Reference capabilities are those the vendors describe publicly. Nothing here claims equivalence of output with a
closed product.

## Charting (reference: TrendSpider, Vela)
| Capability | State | Notes |
| --- | --- | --- |
| Candles, bars, line, area, Heikin-Ashi | IMPLEMENTED | Vela price styles, switchable in the toolbar |
| Hollow candles, Renko, Point & Figure, range bars | PLANNED M2 | Need custom aggregation + Vela chart-type plugins |
| Daily / weekly / monthly | IMPLEMENTED | Weekly/monthly derived from daily; forming periods flagged |
| Intraday, quarterly | PLANNED M2 | Needs intraday provider support |
| Log / linear scale | IMPLEMENTED | |
| Drawing tools, annotations | PARTIAL | Vela's toolbar works; drawings are not saved per user/symbol yet |
| Multi-chart synchronized layouts | PLANNED M2 | `VelaWorkspace` grid |
| Saved layouts / workspaces / presets | PARTIAL | Timeframe, style, scale, indicator set persist in the browser only |
| Anchored VWAP | PARTIAL | Indicator exists (anchor = bar index); no click-to-anchor UI, no ATH anchor yet |
| Volume profile, heatmaps | PLANNED M2 | |
| Fibonacci tools | PARTIAL | Manual via Vela drawings; automatic swing-based Fibonacci is M2 |
| Auto trendlines, support/resistance | PLANNED M2 | |
| Relative-strength ratio, benchmark/sector comparison | PLANNED M2 | |
| Replay mode | PLANNED M2 | Vela exposes `chart.replay`; not wired |
| Screenshot / export | PLANNED M2 | Vela `screenshot()` available |
| Earnings / corporate-action markers | BLOCKED | Needs a licensed events feed |
| Automated pattern recognition (12 pattern families, stages) | PLANNED M2 | With confirmation timestamps and algorithm versions |
| Touch / responsive | PARTIAL | Layout adapts; not tested on devices |

## Indicators and signals (reference: TrendSpider, LuxAlgo toolkits)
| Capability | State | Notes |
| --- | --- | --- |
| SMA, EMA, WMA, VWMA, RSI, MACD, Stochastic, StochRSI, ROC, Williams %R, CCI, MFI, Bollinger, Keltner, Donchian, ATR, HV, ADX/DMI, SuperTrend, Parabolic SAR, OBV, A/D, CMF, volume MA, anchored VWAP | IMPLEMENTED | 25 indicators; 19 golden-tested vs TA-Lib, 6 property-tested; all lookahead-tested |
| Ichimoku, Squeeze Momentum, session VWAP, 52-week / ATH stats, RS vs benchmark | PLANNED M2 | |
| Higher-timeframe indicators | PARTIAL | Scanner supports daily/weekly/monthly operands; chart overlays of other timeframes are M2 |
| Cross-symbol indicators | PLANNED M2 | |
| Legion Adaptive Signals (trend, reversal, trailing stops, clouds, confluence…) | PLANNED M2 | Original, documented, parameterised |
| LuxAlgo Signals & Overlays / Price Action Concepts / Oscillator Matrix outputs | NOT REPRODUCIBLE | Closed-source formulas. Legion suites provide comparable *categories* of function with original rules |
| Market structure (BOS, CHoCH, order blocks, FVG, liquidity sweeps…) | PLANNED M2 | Generic public concepts; each rule documented |
| Composite oscillator with visible contributions | PLANNED M2 | |

## Scanning (reference: TrendSpider scanner)
| Capability | State | Notes |
| --- | --- | --- |
| Technical rules with AND/OR, offsets, multipliers, crosses | IMPLEMENTED | Nested groups in the API; the visual builder edits one level |
| Multi-timeframe conditions | IMPLEMENTED | Daily / weekly / monthly completed bars |
| Ranking, templates, saved scans, watchlist scans | IMPLEMENTED | |
| Conditions displayed before execution | IMPLEMENTED | |
| CSV / JSON export | IMPLEMENTED | |
| Historical screen replay | PARTIAL | Engine accepts an as-of time (tested); no UI/API parameter yet |
| Scheduled scans, shareable results | PLANNED M3 | Needs workers |
| Fundamental screening, custom factor scores | BLOCKED → M3 | Needs a licensed fundamentals feed |
| Point-in-time index membership | BLOCKED | Needs licensed constituent history |
| Natural-language → scan | PLANNED M5 | Must emit the same inspectable schema |
| Legion Command scanners A–K, unified output, action categories | PLANNED M3 | B and K depend on fundamentals; A on breadth/macro data |

## Strategy testing, AI, trading, alerts, SaaS
| Capability | State | Notes |
| --- | --- | --- |
| Strategy builder, event-driven backtester, metrics, validation | PLANNED M4 | |
| AI research agents with tool calls and risk veto | PLANNED M5 | Needs `ANTHROPIC_API_KEY` |
| Paper trading, options research | PLANNED M6 | Options data BLOCKED on a licensed chain feed |
| Live broker execution | PLANNED (disabled) | Only via authorised broker APIs with explicit permission |
| Alerts (price, indicator, pattern; email/webhook/push) | PLANNED M8 | |
| Scheduled reports | PLANNED M3 | |
| Auth, organizations, roles, tenant isolation | IMPLEMENTED | No invitations, email verification or MFA yet |
| Entitlements as configuration | IMPLEMENTED | Limits for existing features only |
| Stripe billing, usage metering, API quotas, admin console | PLANNED M7 | Needs Stripe keys |
| Audit log | PARTIAL | Written for auth and mutations; no viewer |
| Monitoring, backups, load tests | PLANNED M8 | |
