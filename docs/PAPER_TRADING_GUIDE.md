# Paper-trading operating guide (Phase 5)

## Activation checklist: forward paper trading stays OFF until every item is done
1. `paper_start_equity` set explicitly by you.
2. P1-P8 approved in `docs/OWNER_APPROVALS.md` for PARABOLIC_NATIVE, and the approval recorded in `specs/native/PARABOLIC_NATIVE.json` (`entry_confirmation.approved`, `exit_rules`).
3. Authenticated Robinhood read-only test passes on the host (Windows step 13).
4. A genuine report with `publication_status: VERIFIED`, unexpired, with v1.1 evidence, arrives and validates.
5. Walk-forward results for the chosen extension (15/20/30%) reviewed by you.

## Daily operating calendar (America/New_York, NYSE calendar incl. holidays and early closes)
| Window | Action |
|---|---|
| Sun 19:00 | weekly window: ingest the weekly report when it exists; MISSING_WEEKLY_REPORT alert at 21:00 |
| Mon-Fri 09:00-09:30 | daily report window; MISSING_DAILY_REPORT alert at 09:15 |
| 09:30-close | revalidate with fresh quotes (60 s max age); evaluate stock, then options; risk gate; simulated orders only if activated; monitor positions |
| close-close+15 min | settle |
| close+15 min-20:00 | reconcile, then write the journal and risk report to `state/outbox/` for Drive publication |

## Fills (conservative)
- Stock buys: at the ask x (1 + 0.10%). There is no fill without an ask.
- Exits: at the bid. A stop is a trigger, not a guaranteed price: a gap through the stop fills at the open.
- Options: whole structures only, at natural prices.
- Assignment and expiration: guard at DTE <= 1.

## Risk events
1. Any halt (daily -1% / weekly -2% / limit breach) writes `state/RISK_HALT.json` and alerts.
2. New entries stay blocked until `python -m legion.ops resume --confirm`.
3. Open positions are listed for review only. No automatic liquidation procedure is approved.

## Emergency stop
- Windows: `deploy\windows\emergency_stop.ps1`.
- macOS: `deploy/macos/emergency_stop.sh`.
- Any OS: `python -m legion.ops emergency-stop --state <dir>`.

The service exits with code 3 and refuses to start until you delete `EMERGENCY_STOP` by hand.
