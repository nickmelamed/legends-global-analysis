# Reconciliation

The reconciliation week is 2026-09-28 to 2026-10-04. Running `make load` and then
`make reconcile` writes `build/reports/reconciliation.md`, which compares our
unrounded figures with `tests/fixtures/pbi_targets.json`. Money and counts are
rounded to the whole unit and hours to 0.1 before comparing. The targets are <!-- numbers: ok, a precision, not a result -->
never edited.

All 24 targets match except the Riverbend total revenue, which is $1 off
because of how Power BI adds rounded components (R-001). Summit, the required
venue, matches on all eight measures. R-002 to R-004 explain where other
Power BI visuals differ from the app. None of them is a target miss.

## R-001: Riverbend total revenue is $1 below the target

| | Ticket | F&B | Merch | Private events | Total |
|---|---|---|---|---|---|
| Ours (unrounded) | 23,777.58 | 3,530.61 | 2,585.56 | 26,324.82 | 56,218.57 |
| Target | 23,778 | 3,531 | 2,586 | 26,325 | 56,220 |

Each component matches after rounding. The target total equals the sum of the
four rounded components (23,778 + 3,531 + 2,586 + 26,325 = 56,220). Our total
is the sum of the unrounded components, rounded once, which gives 56,219.

The query is `WEEK_SQL` in `pipeline/reconcile.py`, venue RTL, which sums
`daily_tickets`, `daily_pos`, `daily_private_events` for the week. The rows
are every countable RTL ticket line, every non-void RTL POS line and the RTL
Definite events in the week. No row is in dispute. The gap is $1 and comes
from rounding order alone.

We keep the unrounded sum. A total that changes with the display precision of
its parts is wrong, and the error grows as more parts are added, for example
when venues are summed into a portfolio total.

## R-002: Ancillary visual shows Summit F&B $1,251.02 lower

The Power BI Ancillary visual shows Summit Restaurant at $4.5K. Our outlet <!-- numbers: ok, Power BI display figures -->
split for the week is Restaurant 5,784.28, Bar 1,251.02, Cafe 2,195.12 and
Gift Shop 6,957.12. Restaurant minus Bar is 4,533.26, which displays as
$4.5K, and Bar is then shown again on its own. The visual's F&B is therefore <!-- numbers: ok, Power BI display figures -->
7,979.40, against the 9,230 target and our 9,230.42. The headline, per cap
and percent change on the same page fit the same reading (DATA_PROFILE.md,
Power BI cross-checks).

The query is `OUTLET_SQL` in `pipeline/reconcile.py`, venue SSD. The rows are
the SSD Bar lines in the week, which sum to 1,251.02. That is the gap.

The packet defines F&B as Restaurant, Bar and Cafe, and the 9,230 target uses
the full sum, so the app shows 9,230.42 (D-008). This is inferred from the
arithmetic without the .pbix file.

## R-003: Revenue by channel leaves out Affiliate

Power BI's revenue-by-channel visual sums to about $61.0K. Our Summit ticket
revenue without Affiliate is 60,894.59, and Affiliate is 681.12 from 10 lines
(SSD-T0042214 and nine others, listed in DATA_PROFILE.md). Every other
channel matches. Pass has $0 and appears in neither chart. A Top 7 filter
would explain it, and the data cannot tell that from a deliberate exclusion.
The app's channel chart follows Power BI and carries a note with the
Affiliate amount (D-007). The query is `CHANNEL_SQL`, venue SSD.

## R-004: Productivity 3.82 against Power BI's 3.81

Our Summit guests per labor hour is 3.8165, from 1,849 guests and 484.47
hours, which displays as 3.82. Showing 3.81 needs 484.67 to 485.94 hours.
Rounding each shift to 0.1 h before summing lands in that range, at 485.00
hours rounding half to even and 485.40 rounding half up (3.812 and 3.809
guests per hour). DATA_PROFILE.md gives a slightly lower figure for the
same idea, because pandas rounds the binary float and some half tenths
round down. Every
variant tried displays 3.81, so per-shift rounding is the likely cause, but
which rounding Power BI uses is not known without the .pbix file. The hours
target (484.5) matches the unrounded sum, so the app shows 3.82.

The query is `SHIFT_ROUNDED_HOURS_SQL` in `pipeline/reconcile.py`, venue SSD,
over the 79 Summit shifts in the week, 15 of which end in a half tenth.
