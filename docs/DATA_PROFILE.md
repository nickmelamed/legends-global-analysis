# Data profile

Profile of the five supplied workbooks. Each
figure here is printed by one of three scripts, run from the repo root with
pandas and openpyxl. Each takes 15 to 60 seconds.

```bash
python3 scripts/profile/ticketing.py         # 01_Ticketing.xlsx
python3 scripts/profile/pos.py               # 02_POS_FandB_Merch.xlsx
python3 scripts/profile/events_labor_ref.py  # 03, 04 and 05
```

The reconciliation week is 2026-09-28 to 2026-10-04. "Summit week" below
means Summit Sky Deck (SSD) in that week. RTL is Riverbend Tower Lookout
(Nashville) and TRO is Three Rivers Observatory (Pittsburgh).

## Summary

One rule set reproduces every Power BI target for all three venues, except
one $1 gap in the Riverbend total that comes from Power BI adding rounded
components. Profiling found three things the spec did not expect. POS has no
duplicate loads, and its repeated rows are real lines. POS timestamps are all
local, and the UTC timestamps are in the NT ticketing feed instead. The
Ancillary visual in the Power BI export understates F&B by subtracting Bar
twice.

| Venue | Measure | Ours | Target | Status |
|---|---|---|---|---|
| SSD | Attendance | 1,849 | 1,849 | match |
| SSD | Ticket revenue | 61,575.71 | 61,576 | match |
| SSD | F&B revenue | 9,230.42 | 9,230 | match |
| SSD | Merch revenue | 6,957.12 | 6,957 | match |
| SSD | Private events | 6,565.00 | 6,565 | match |
| SSD | Total revenue | 84,328.25 | 84,328 | match |
| SSD | Labor hours | 484.47 | 484.5 | match |
| SSD | Payroll | 9,346.69 | 9,347 | match |
| RTL | Att / Tix / F&B / Merch / PE | 883 / 23,777.58 / 3,530.61 / 2,585.56 / 26,324.82 | 883 / 23,778 / 3,531 / 2,586 / 26,325 | match |
| RTL | Total revenue | 56,218.57 | 56,220 | $1 after rounding, see below |
| RTL | Hours / payroll | 358.69 / 6,942.10 | 358.7 / 6,942 | match |
| TRO | Att / Tix / F&B / Merch / PE | 771 / 20,282.95 / 2,768.78 / 1,979.46 / 17,564.55 | 771 / 20,283 / 2,769 / 1,979 / 17,565 | match |
| TRO | Total revenue | 42,595.74 | 42,596 | match |
| TRO | Hours / payroll | 321.17 / 6,257.93 | 321.2 / 6,258 | match |

The RTL total target of 56,220 is the sum of the rounded components
(23,778 + 3,531 + 2,586 + 26,325). The unrounded sum is 56,218.57, which
rounds to 56,219. The total is a derived figure, so this belongs in
docs/RECONCILIATION.md in Phase 2 as a rounding difference.

The rules that reproduce the targets:

- Tickets: drop duplicate `ticket_line_id` loads keeping the latest
  `ingestion_ts`, drop status Cancelled (LT) and CANCELLED (NT), drop package
  classes NON-ADMISSION and EVENT, filter on `event_date`, then sum `quantity`
  and `ticket_value`.
- POS: keep every row, exclude `is_voided = Y`, take
  `item_quantity * item_price - discount_amount`, and assign each line to
  the business day of `order_created_date` minus 4 hours. Restaurant, Cafe and
  Bar are F&B, and Gift Shop is merchandise.
- Labor: attribute each shift to `date` (the start date), sum `total_hrs` and
  `total_earnings`, count missing-rate shifts at $0, and leave out tips.
- Private events: Definite status only, event-level `grand_total` on
  `event_date`.

## Hypotheses

| # | Hypothesis | Status | Evidence | Rows affected | Summit-week impact | Rule for Phase 2 |
|---|---|---|---|---|---|---|
| 1 | Duplicate loads | Confirmed for tickets. Rejected for POS. | Tickets have 262 NT `ticket_line_id` values loaded twice, all SSD on 2026-06-06 and 06-07, identical except `ingestion_ts` (e.g. SSD-T0032692). POS has no load timestamp. Its 4,042 exact-copy rows are real lines, because the order `subtotal` matches the line sum for all 76,328 orders only when they are kept. | 262 ticket rows (858 guests, $30,440.88). POS none. | 0. Dropping POS copies would wrongly remove $417.56. | Dedup tickets on `ticket_line_id`, keep latest. Never dedup POS rows. |
| 2 | LT and NT status vocabularies differ | Confirmed, framing corrected | Cancelled lines keep full quantity and value. `record_status` is ACTIVE on every row. The status text is the only signal. LT is the unreliable vocabulary, with 92% of lines "In Process". | 1,252 LT and 840 NT cancelled lines | -80 guests, -$1,944.58 (11 lines) | Per-source cancelled denylist. Keep No Show, NO_SHOW, PART_REDEEMED and In Process. |
| 3 | Add-ons and event entries are not admissions | Confirmed | NON-ADMISSION (photo, parking) carries value. EVENT (Private Event Entry) is $0 with quantity. Annual Pass visits ($0) do count. | 902 event-entry lines plus all add-on lines | -112 guests, -$1,330.20 | Exclude classes NON-ADMISSION and EVENT. |
| 4 | Cutover changes names and channels, class is stable | Partial | Names change for 14 of 17 packages. `package_class` and `internal_name` are stable. Channels do not change (same merchant ids, same mix). Prices rose 4.5% on 2026-01-01, before the cutover. | 102 dim_package rows | 0 | Compare last year by `package_class`. Flag the price rise in last-year deltas. |
| 5 | POS order totals repeat per line | Confirmed | Order-level money has one value per order. `final_total = subtotal + tax + gratuity` and `subtotal` = non-void net line sum, to the cent, for all 76,328 orders. Gratuity is 20% on Bar and Restaurant orders. | All POS rows | 0 under the line rule. `final_total` would give F&B 10,780.27. | Line revenue. Order subtotal is a test check. |
| 6 | Some POS timestamps are UTC | Rejected for POS. UTC found in NT tickets. | Each outlet has sharp local opening hours (Cafe 09:00 to 19:59, Gift Shop 10:00 to 20:59, nothing outside them), and all six F&B and merch targets match with no conversion. A UTC subset would show sales hours shifted by 5 to 7 hours. NT `event_time` is UTC, but `event_date` is already the local date on 100% of rows. The 4 AM cutoff moves 431 POS rows. | 431 POS rows cross midnight | 0 for SSD. One RTL Bar order ($14.50, 00:33 on 10-05) moves into the week, which RTL needs to match. | Business day = local timestamp minus 4 h. Use `event_date` for tickets, and convert NT `event_time` from UTC only if times are shown. |
| 7 | Messy labels | Rejected for POS. Confirmed for labor. | POS labels are clean. Labor has 24 department labels that map to 6 departments with 0 unmapped ("Food & Beverage" holds only restaurant positions). There are 12 `location_name` variants of 3 names. Position is clean. | 16,512 labor and 16,450 schedule rows | Department split only | Mapping table. Fail the load on unmapped values. |
| 8 | Labor rules | Partial | `date` is always the start date (639 overnight shifts). `total_hrs = reg_hrs + ot_hrs` always. Clock time is 0.5 h more on 12,004 rows (unpaid break). OT is paid at 1.5x. 132 rows have no rate or earnings. One business-key duplicate (SSD, 2026-01-06). 237 shifts overlap the same person's previous shift, 174 of them unscheduled covers. | 132 missing-rate rows, 237 overlaps | 2 missing-rate shifts (12.98 h) at $0, 2 overlaps (11.0 h) counted, tips $513.86 excluded | Start date. `total_hrs`. Missing rate counts $0 and the window's payroll is marked incomplete (D-006). Cover shifts count. No tips. |
| 9 | Multi-day bookings repeat the booking total | Confirmed | 34 two-day bookings. `booking_grand_total` equals the sum of event `grand_total` for all 425 bookings. Summing per row overstates by $736,246.60. The week cannot tell the rules apart, but the prior week's -70.5% only fits event-level money. | 68 event rows | 0 (1 event, EV-000222) | Event-level `grand_total` on `event_date`, Definite only. |
| 10 | Missing venue-days | Confirmed | RTL 2026-04-18 (Saturday) has no ticket and no POS rows, but has labor. Bar outlet gaps on days with other POS rows: RTL 26 (27 counting 2026-04-18, when the whole venue is missing, and including 10-02 in the week), TRO 67, SSD 2. Labor, schedule, budget and weather have no gaps. | 1 venue-day, plus outlet-days | 0 | Show "no data" for a venue-day missing from a feed (D-005). Bar outlet gaps show $0 (D-007). |
| 11 | Other | Found | See the list below. | | | |

Other findings (hypothesis 11):

- `retail_amount` is the base adult price times quantity, not the line value.
  `ticket_value` is the revenue field.
- Free Admission Day appears once, at RTL on 2026-05-09 (142 lines, $0).
- Voids all carry the same one reason (1,973 lines). Including them
  would add $138.48 to Summit-week F&B and $76.96 to merch.
- Voucher is a POS tender, so voucher sales count as revenue.
- The budget has no Bar department, and `budget_attendance` is set only on
  Ticket rows.
- Weather ends 2026-10-04, so the cache has no forward days.
- `booking_definite_date` runs to 2026-10-17, after APP_TODAY. Two Definite
  bookings (one RTL, one TRO, events in November) are affected. No KPI uses
  this column, so the cause is left unexplained.
- `pay_period_flag = Current` marks exactly the reconciliation week.
- Unscheduled shifts are 5.0 h on the clock and 4.5 h paid, an undocumented
  deduction.

## Power BI cross-checks

The Ancillary visual shows Restaurant 4.5K, Bar 1.3K, Cafe 2.2K and Gift Shop
7.0K. Our Summit-week split is Restaurant 5,784.28, Bar 1,251.02, Cafe
2,195.12 and Gift Shop 6,957.12. The visual's Restaurant equals Restaurant
minus Bar (4,533.26), so Bar is subtracted twice. Three other figures on the
page fit the same reading. The headline $14.9K is 16,187.54 minus 1,251.02.
The per cap $8.08 is 14,936.52 / 1,849. The +24.6% vs prior only works with
prior-week Bar removed the same way. The 9,230 target is the full F&B sum, and
the visual understates F&B by $1,251.02. This is inferred from the arithmetic
without the .pbix. Avg Check $38.40 and Capture Rate 31.8% do not
reproduce and are unexplained. The other candidate, Restaurant minus its own
alcohol, gives 4,696.86 ($4.7K) and does not fit.

Revenue by sales channel sums to $60,894.59 for the top seven channels. The
gap to $61,575.71 is exactly Affiliate, $681.12 from 10 lines (SSD-T0042214
and nine others). Every channel's revenue and ATP match the export. Pass has
$0 and appears in neither chart. A Top 7 filter on the revenue visual and a
hide-zero filter on the ATP visual would explain both. The data cannot tell a
Top N filter from a deliberate Affiliate exclusion.

Productivity 1,849 / 484.47 is 3.8165, which rounds to 3.82, not the 3.81
shown. A displayed 3.81 needs 484.67 to 485.94 hours. Rounding each shift to
0.1 h before summing gives 484.90, and 1,849 / 484.90 is 3.813. This is the
only candidate found in that range, so it is likely but not proven. The hours
target of 484.5 uses unrounded shifts. Labor $/guest of $5.05 confirms
payroll of 9,346.69 with missing rates left at $0.

The private events monthly chart stops at 2026-08 even though September 2026
has 6 Definite Summit events ($46,402). The chart's top gridline ($179.9K) is
1.15 times the June Definite total ($156,456), so it plots Definite
event-date revenue. The cut at 2026-08 is a date filter or fixed range in the
report. The exact filter is unexplained without the .pbix.

Further Summit checks that match the export: all 35 daily attendance figures
in the five-week calendar, prior week attendance 1,651 (+12.0%) and revenue
+22.3%, ATP $33.30, package class mix 74/16/9/1, and department hours on the
Labor page. Guest Insights figures (premium 27%, same day 38%, basket 2.6),
the Private Events "Event Count 4" and the Labor page $/hr (off by $0.01 to
$0.03) are unexplained.

## Detail by workbook

### 01_Ticketing.xlsx

README sheet says the extract is order-line grain (one row is one package on one order, `quantity` guests), event_date 2025-01-01 to 2026-10-04 plus advance sales to 2026-11-03, LT until 2026-02-02 and NT from 2026-02-03.

#### fact_ticket

83,191 rows, 21 columns. LT 48,780 rows, NT 34,411 rows.

Candidate key `ticket_line_id` is not unique: 82,929 distinct values, 262 ids appear twice (see H1). No row is an exact duplicate because `ingestion_ts` differs. After keeping the latest load, `ticket_line_id` is unique. `order_id` groups several lines. The `ticket_line_id` prefix always equals `attraction_prefix`. Every `package_id` exists in dim_package and belongs to the same venue and source system as the fact row. Every `merchant_id` exists in dim_merchant. `attraction_prefix` and `location_id` map one to one (SSD L-1001, RTL L-1002, TRO L-1003), matching dim_venue.

`promotional_code` has 80,398 nulls and `o_device` 58,809. No other column has nulls.

Distinct values (LT / NT row counts):

| Column | LT | NT |
|---|---|---|
| ticket_status | In Process 45,087, Redeemed 2,200, Cancelled 1,252, No Show 241 | CONFIRMED 20,044, REDEEMED 11,118, NO_SHOW 1,532, PART_REDEEMED 865, CANCELLED 852 |
| record_status | ACTIVE 48,780 | ACTIVE 34,411 |
| attraction_prefix | SSD 25,138, RTL 13,860, TRO 9,782 | SSD 17,879, RTL 9,611, TRO 6,921 |
| promotional_code | null 47,151, TEACHER 422, BDAY5 415, LOCAL25 397, SUMMER10 395 | null 33,247, BDAY5 307, LOCAL25 302, SUMMER10 282, TEACHER 273 |
| customer_country | guest data, no nulls, distribution not profiled | |
| o_device | null 34,446, Mobile 8,951, Desktop 4,512, Tablet 871 | null 24,363, Mobile 6,340, Desktop 3,097, Tablet 611 |
| merchant_id | 1: 14,673, 2: 14,334, 3: 4,532, 10: 3,556, 8: 2,777, 7: 2,692, 4: 2,167, 5: 1,727, 6: 1,487, 9: 835 | 1: 10,580, 2: 10,048, 3: 3,114, 10: 2,442, 7: 1,974, 8: 1,839, 4: 1,496, 5: 1,248, 6: 1,019, 9: 651 |

The two status vocabularies are the same concepts in different case and separators (Cancelled / CANCELLED, Redeemed / REDEEMED, No Show / NO_SHOW). NT adds PART_REDEEMED. LT has In Process, NT has CONFIRMED. No other categorical column has variant spellings.

Date ranges by source system:

| Column | LT | NT |
|---|---|---|
| event_date | 2025-01-01 to 2026-02-02 | 2026-02-03 to 2026-11-03 |
| event_time | 2025-01-01 09:15 to 2026-02-02 20:45 | 2026-02-03 14:00 to 2026-11-03 15:00 |
| date_sold | 2024-10-07 to 2026-02-02 | 2025-11-08 to 2026-10-04 |
| ingestion_ts | 2025-01-02 06:00 to 2026-02-03 06:00 | 2026-02-04 06:00 to 2026-10-05 06:00 |

The cutover is clean on event_date. No LT row falls after 2026-02-02 and no NT row before 2026-02-03. NT sold tickets from 2025-11-08 for post-cutover dates.

No quantity or value is negative. `quantity` 1 to 40. `ticket_value` and `retail_amount` are zero on the same 8,691 rows (before dedup).

#### dim_package

102 rows, no nulls, `package_id` unique. 17 packages per venue per source system (3 venues x 2 systems). `package_name` changes at the cutover, `internal_name` and `package_class` do not (see H4).

package_class per system: INDIVIDUAL 24, FIT 6, GROUP 6, NON-ADMISSION 6, PROMOTION 6, EVENT 3. ticket_type per system: GENERAL ADMISSION 30, PREMIUM 12, ADD-ON 6, EVENT 3. is_season_pass is 1 only for `pass` (Annual Pass Visit), 3 rows per system.

Name pairs that are the same package (LT name / NT name): Adult GA / General Admission - Adult, Child GA (3-12) / General Admission - Child, Senior GA 65+ / General Admission - Senior, Military GA / General Admission - Military, Sunset Experience / Sunset Hour Experience, Express Entry / Express Entry - Skip the Line, VIP Champagne Experience / VIP Experience w/ Champagne, Annual Pass Visit / Annual Pass - Visit, 2-for-1 Local Promo / Local Resident 2-for-1, Tour Operator Day Rate / FIT - Day Rate (Net), Tour Operator Combo / FIT - Premium Combo (Net), School Group / Group - School, Corporate Group 10+ / Group - Corporate 10+, Souvenir Photo / Souvenir Photo Package. Unchanged: Free Admission Day, Parking Validation, Private Event Entry.

#### dim_merchant

10 rows, no nulls, `merchant_id` unique. Nine sales channels. OTA has two merchants (OTA Partner A id 5, OTA Partner B id 6). The other channels have one merchant each: Walk Up (Gate Terminal), Web (Online Store), Pass (Annual Pass Gate), Group (Group Sales Desk), Voucher (Voucher Redemption), Concierge (Hotel Concierge Network), Affiliate (Affiliate Network), Terminals (Self-Serve Kiosk). Merchant ids are shared by LT and NT, so channels do not change at the cutover.

#### Hypotheses

**H1 duplicate loads. CONFIRMED.** 262 `ticket_line_id` values appear exactly twice (524 rows), all NT, all SSD, event_date 2026-06-06 (156 ids) and 2026-06-07 (106 ids). The first copy was ingested 2026-06-07 06:00 or 2026-06-09 06:00 and the second 2026-06-08 06:00. Every column except `ingestion_ts` is identical within each pair, so keep-latest and keep-first give the same result. Examples SSD-T0032692, SSD-T0032693, SSD-T0032694. Dedup drops 262 rows, worth 858 countable guests and $30,440.88 of countable ticket value on Summit 2026-06-06/07. Reconciliation week impact is zero (no duplicates in that week). It matters for any window covering early June, including next year's last-year comparisons.

**H2 status vocabularies differ. CONFIRMED, with a correction to the framing.** Cancelled lines keep their full quantity and value in both systems. There is no negative quantity, no zeroed value and no record_status signal (record_status is ACTIVE on every row). The only cancellation signal is the status text: LT `Cancelled` (1,252 lines, $142,002 value) and NT `CANCELLED` (840 lines after dedup, $102,379). LT is the unreliable vocabulary. 92% of its lines are `In Process` and only 4.5% are `Redeemed`, so an allowlist such as "Redeemed only" would drop most real LT visits. NT statuses look like a real lifecycle. The rule that reconciles is a per-source denylist of the cancelled status, keeping NO_SHOW and PART_REDEEMED and LT In Process and No Show. Dropping NO_SHOW as well misses the target by 77 guests and $2,240 at Summit. Summit week impact of the cancel rule: 11 cancelled admission lines, 80 guests, $1,944.58 (example SSD-T0042290, SSD-T0042317, SSD-T0042361). Whether an LT `In Process` line from 2025 is really a visit cannot be checked from this file. That uncertainty applies to last-year comparisons only.

**H3 add-ons and private event entries. CONFIRMED.** NON-ADMISSION (Souvenir Photo, Parking Validation, ticket_type ADD-ON) carries ticket value. EVENT (Private Event Entry) is always zero value but carries quantity (902 lines, 3,182 guests in total). Both must leave attendance and ticket revenue. Summit week, non-cancelled, photo is 15 lines, 66 qty, $1,069.20. Parking is 8 lines, 29 qty, $261.00. pe_entry is 5 lines, 17 qty, $0. Total impact 112 guests and $1,330.20 of revenue. The Annual Pass Visit (`pass`, INDIVIDUAL, zero value) does count as attendance: excluding it gives 1,781 against 1,849.

**H4 cutover changes names, not classes or channels. PARTIAL.** Package names change for 14 of 17 packages per venue. `package_class` and `internal_name` are identical across LT and NT for every venue, so class (or internal_name for finer grain) is a stable key. Channels do not change: merchant ids and the channel mix are the same in both systems (Walk Up 30.1% / 30.7%, Web 29.4% / 29.2%, others within 0.3 points). The time convention does change (see H11 timezone). Separately, prices rose on 2026-01-01, a month before the cutover. SSD Adult GA was $36.00 in 2025 and $37.62 from 2026-01-01 in both LT and NT. A last-year comparison therefore mixes a 4.5% price increase with any volume change. No Summit week impact.

**H10 missing venue-days. CONFIRMED, one day.** Over 2025-01-01 to 2026-10-04 the only venue-day with no ticket rows is RTL (Nashville) 2026-04-18, a Saturday. SSD and TRO have every day. The thinnest days with data are TRO 2025-05-13 (2 lines), TRO 2025-01-16, 2025-04-21 and 2026-09-03 (4 lines each), which look like quiet days rather than gaps but are not proven. Advance-sale dates after 2026-10-04 have many empty days, which is expected. No Summit week impact.

**H11 other findings.**

1. NT `event_time` is UTC, LT `event_time` is venue local. Converting NT event_time from UTC to the venue timezone gives event_date on 100% of rows, while the raw NT date matches event_date on only 80.0%. Raw NT hours run 13 to 23 and 0 to 3. Local visit times are 08:00 to 21:xx, so the 4 AM business-day cutoff never moves a ticket. `event_date` is already the local business date in both systems and is the column to use. Using the raw UTC date instead costs Summit 1 guest and $160.23 for the week.
2. `retail_amount` is not the admission amount. It equals the base adult price times quantity for almost every package (SSD $36.00 or $37.62 per guest for child, senior, VIP, group alike), while `ticket_value` varies by package. They agree on only 44.6% of lines. `ticket_value` is the field that reconciles, as the dictionary says.
3. `Free Admission Day` (promo_free) appears once, at RTL on 2026-05-09, 142 lines, zero value. It counts as attendance under the reconciled rule. Counted as attendance (D-004).
4. Guest Insights page figures do not reproduce with obvious definitions. Power BI shows premium rate 27%, same-day rate 38%, lead time 6.4 d, basket 2.6. Under the reconciled filter, premium share is 19.0% by guests or 22.3% by lines (32.6% by revenue), same-day share is 43.9% by guests or 61.2% by lines, mean lead time 6.2 d by lines, guests per order 4.88. Unexplained. These are not on the Overview page.
5. The private event ticket line (pe_entry) has quantity in the ticketing feed. If private events revenue is taken from the CRM, those guests are not visitors in this feed and must not be added to attendance either.

#### Reproduction of the reconciliation week

Rule set that matches all three venues exactly: dedup on `ticket_line_id` keeping latest `ingestion_ts`, drop status Cancelled (LT) and CANCELLED (NT), drop package_class NON-ADMISSION and EVENT, window on `event_date` 2026-09-28 to 2026-10-04, attendance = sum(quantity), ticket revenue = sum(ticket_value).

| Venue | Attendance | Target | Ticket revenue | Target |
|---|---|---|---|---|
| SSD | 1,849 | 1,849 | 61,575.71 | 61,576 |
| RTL | 883 | 883 | 23,777.58 | 23,778 |
| TRO | 771 | 771 | 20,282.95 | 20,283 |

Summit alternatives (attendance / revenue / revenue gap): keep cancelled 1,929 / 63,520.29 / +1,944.29. Keep add-ons and event entries 1,961 / 62,905.91 / +1,329.91. Keep both 2,041 / 64,850.49 / +3,274.49. Also drop NO_SHOW 1,772 / 59,335.86 / -2,240.14. Also drop Annual Pass 1,781 / 61,575.71. UTC date for NT 1,848 / 61,415.77 / -160.23. Dedup on or off makes no difference in this week. Full grid for all venues in the script output.

Further checks of the same rule against the Power BI export for Summit: the five-week attendance calendar (2026-08-31 to 2026-10-04) matches all 35 daily figures. Prior week 2026-09-21 to 27 gives 1,651 guests and $50,339.33, so +12.0% attendance and +22.3% revenue, matching the export. ATP $33.30 matches. Revenue mix by class INDIVIDUAL 74.1%, GROUP 15.9%, FIT 8.8%, PROMOTION 1.2% matches 74/16/9/1.

#### Revenue by sales channel cross-check (Summit, week)

| Channel | Revenue | Guests | Lines | ATP |
|---|---|---|---|---|
| Web | 19,064.72 | 457 | 128 | 41.72 |
| Walk Up | 18,890.94 | 448 | 139 | 42.17 |
| Group | 9,788.40 | 466 | 18 | 21.01 |
| OTA | 3,664.08 | 129 | 35 | 28.40 |
| Terminals | 3,275.16 | 83 | 26 | 39.46 |
| Concierge | 3,124.56 | 90 | 23 | 34.72 |
| Voucher | 3,086.73 | 77 | 23 | 40.09 |
| Affiliate | 681.12 | 31 | 10 | 21.97 |
| Pass | 0.00 | 68 | 41 | 0.00 |

Total 61,575.71. Every channel figure and ATP matches the export (Concierge ATP 34.72 against 34.71 shown, a rounding difference of under a cent). The revenue-by-channel bar chart shows the top seven channels, which sum to $60,894.59 (about 61.0K as the export reads). The gap to 61,576 is exactly Affiliate, $681.12 from 10 lines (SSD-T0042214, -42219, -42306, -42251, -42426, -42455, -42497, -42462, -42616, -42632, packages Local Resident 2-for-1 and FIT - Day Rate). Pass has $0 revenue and is missing from both charts. The likely cause is a Top N = 7 filter on the revenue visual, and an ATP visual that hides channels with zero revenue. Both are hidden visual-level filters. The data cannot tell a Top N filter from an explicit Affiliate exclusion, so this is an inference.

#### Open questions

Resolved in D-004, D-005 and D-007.

### POS lines (data/02_POS_FandB_Merch.xlsx, sheet pos_order_lines)

"Week" means business days 2026-09-28 to 2026-10-04, where the business day is `order_created_date - 4h`, then the date.

#### Shape and keys

131,428 rows, 16 columns, 76,328 distinct `order_id`. The README sheet says only that the sheet holds POS lines for Restaurant, Cafe, Bar (F&B) and Gift Shop (merchandise) and that subtotal, tax, gratuity and final_total repeat on every line of an order.

There is no line number and no ingestion or load timestamp column. No column set is a unique line key. `order_id + product_name` repeats on 7,529 rows, and even the full 16-column row repeats on 4,042 rows. `order_id` is the order key. Every order has exactly one venue_code, outlet, order_created_date, tender_type, subtotal, tax, gratuity and final_total. The order_id prefix always equals venue_code.

Only `voided_reason` has nulls (129,455, exactly the non-voided rows). Timestamps are minute precision (no non-zero seconds).

#### Distinct values

| column | values (row counts) |
|---|---|
| venue_code | SSD 75,017, RTL 34,481, TRO 21,930 |
| outlet | Cafe 44,954, Restaurant 38,200, Gift Shop 33,070, Bar 15,204 |
| product_category | Food 49,660, Retail 33,070, Beverage 28,186, Alcohol 20,512 |
| is_voided | N 129,455, Y 1,973 |
| voided_reason | free text, 1,973 non-null, one distinct value, not quoted here |
| tender_type | Card 105,403, Cash 10,404, Voucher 9,133, Gift Card 6,488 |
| item_quantity | 1: 98,449, 2: 26,291, 3: 6,688 |
| product_name | 31 values, all distinct spellings (see script output) |

Outlet by category: Bar has Alcohol 10,192, Beverage 2,504, Food 2,508. Cafe has Beverage and Food only. Gift Shop is Retail only. Restaurant has Alcohol 10,320, Beverage 3,580, Food 24,300. Every venue and product pair has exactly two distinct prices (93 pairs), which looks like one price change. Not investigated further.

No alternate spellings, case variants or whitespace variants exist in venue_code, outlet, product_category, tender_type or product_name. There is no department column and no timezone marker column in this sheet.

#### Date ranges

All twelve venue and outlet pairs run from 2025-01-01 to 2026-10-04 local time. The only row after midnight on 2026-10-04 is RTL Bar 2026-10-05 00:33 (one Bar order), which belongs to business day 2026-10-04.

#### Hypotheses

**H1 duplicate loads. REJECTED for this sheet.** The column the hypothesis needs (ingestion_ts) does not exist. 4,042 rows are exact copies of another row (SSD 2,318, RTL 1,046, TRO 678, in 3,978 orders). The POS-exported `subtotal` proves they are real lines. Subtotal equals the sum of non-void `qty * price - discount` for all 76,328 orders when the copies are kept, and for only 72,351 when they are dropped (3,977 orders break). The copies are interleaved with their originals, not appended at the end. Dropping them would remove $417.56 of non-void net from Summit week (F&B 9,033.34 and merch 6,736.64 instead of 9,230.42 and 6,957.12) and miss the targets. Keep every row. Summit-week impact of the correct treatment is $0.

**H5 order-level columns repeat. CONFIRMED.** All four order-level money columns have one value per order. `final_total = subtotal + tax + gratuity` for all 76,328 orders. `subtotal = sum over non-void lines of (item_quantity * item_price - discount_amount)` for all 76,328 orders, to the cent. Including void lines breaks 1,962 orders, and using gross before discount breaks 6,140. So the line rule and the order rule agree everywhere, and summing subtotal across lines would multiply it by the line count. Gratuity is 20% of subtotal on 4,966 Bar and 9,070 Restaurant orders and zero elsewhere. Tax is about 8.2% to 8.3% of subtotal at all three venues. Summing subtotal per line would overstate Summit-week revenue. Using final_total would give F&B 10,780.27 and merch 7,531.13.

**H6 mixed UTC and local timestamps. REJECTED.** Hours run 09 to 23 plus 00 and 01. No row falls between 02:00 and 08:59 at any venue. The per-outlet hour profile has sharp edges (Cafe 09:00 to 19:59, Gift Shop 10:00 to 20:59, Restaurant 11:00 to 21:59) with nothing outside them. A UTC subset of daytime sales would show Cafe or Gift Shop rows 5 to 7 hours later, and there are none. All six targets also match with no conversion. All rows look local. The 4 AM cutoff still matters. 431 rows fall before 04:00 (SSD 240, RTL 121, TRO 70). For Summit week, 2 rows (one order) move to the previous day but stay inside the week, so the weekly impact is $0 (calendar day and business day both give 16,187.54). For Riverbend, one Bar order ($14.50) moves from 2026-10-05 into the week, and that is the only reason RTL F&B is 3,530.61 (matches 3,531) and not 3,516.11 by calendar date.

**H7 messy labels. REJECTED for this sheet.** Every label column is clean (see the table above). Proposed mapping is identity plus department. `Restaurant`, `Cafe` and `Bar` map to F&B, and `Gift Shop` maps to Merchandise. The budget and the Overview page split F&B into Restaurant and Cafe only, so Bar is reported under Restaurant (D-003). Nothing is unmapped.

**H10 missing venue-days. PARTIAL.** At venue level only RTL 2026-04-18 has no rows at all (every outlet missing). SSD and TRO have rows every business day from 2025-01-01 to 2026-10-04. Per outlet, gaps are mostly Bar days. RTL Bar 27 days, including 2026-10-02 in the reconciliation week, SSD Bar 2 days (2025-04-21, 2025-09-22), TRO Bar 67 days, TRO Restaurant 14, TRO Gift Shop 4, TRO Cafe 1, RTL Restaurant 3 (2025-01-20, 2025-09-04, 2026-04-18). Full lists are in the script output. Low-volume Bar days could be genuinely zero sales, and this sheet cannot tell a closed outlet from a missing feed. Summit week has no gaps. RTL 2026-04-18 should show "no data", not zero.

**H11 other findings.**
- Voids. 1,973 lines are voided, all with the same one reason. 87 voided lines also carry a discount. Voided lines are excluded from subtotal. In Summit week, including them would add $138.48 to F&B and $76.96 to merch.
- Discounts reduce revenue (Summit-week F&B gross 9,265.36 vs net 9,230.42).
- Voucher is a tender type, not a discount. Voucher orders are inside the subtotal and the matched targets, so vouchers count as revenue.
- No negative prices, negative discounts or discounts above line gross.
- Bar sells Food (Bar Snacks) and Restaurant sells Alcohol, so product_category cannot stand in for outlet.

#### Reproducing Summit F&B 9,230 and merch 6,957

| rule set | SSD F&B / merch | RTL | TRO |
|---|---|---|---|
| business day, keep copies, exclude voids, net of discount | **9,230.42 / 6,957.12** | **3,530.61 / 2,585.56** | **2,768.78 / 1,979.46** |
| same, order subtotal counted once | 9,230.42 / 6,957.12 | 3,530.61 / 2,585.56 | 2,768.78 / 1,979.46 |
| calendar day instead of business day | 9,230.42 / 6,957.12 | 3,516.11 / 2,585.56 | 2,768.78 / 1,979.46 |
| gross (before discount) | 9,265.36 / 7,000.24 | 3,548.48 / 2,604.21 | 2,776.27 / 1,981.32 |
| include voids | 9,368.90 / 7,034.08 | 3,573.07 / 2,624.91 | 2,807.01 / 2,047.65 |
| drop exact copies | 9,033.34 / 6,736.64 | 3,386.15 / 2,488.20 | 2,708.34 / 1,951.56 |
| subtotal + gratuity | 10,018.75 / 6,957.12 | 3,823.38 / 2,585.56 | 2,967.03 / 1,979.46 |
| subtotal + tax | 9,991.94 / 7,531.13 | 3,821.89 / 2,798.89 | 2,997.20 / 2,142.73 |
| final_total | 10,780.27 / 7,531.13 | 4,114.66 / 2,798.89 | 3,195.45 / 2,142.73 |

Only the first rule set matches all six targets after rounding. UTC conversion is a no-op because no rows are UTC. The 4 AM cutoff is needed for RTL.

#### Ancillary visual cross-check (Summit week)

Our outlet split (non-void net, business day) is Restaurant 5,784.28, Bar 1,251.02, Cafe 2,195.12, Gift Shop 6,957.12, total 16,187.54. Bar ($1.3K), Cafe ($2.2K) and Gift Shop ($7.0K) match the visual. Restaurant does not. The visual shows $4.5K and we have $5.8K.

The visual's Restaurant equals our Restaurant minus our Bar (5,784.28 - 1,251.02 = 4,533.26, which displays as $4.5K). Three independent figures on the same page fit this reading.

- The headline "Ancillary Revenue $14.9K" equals 16,187.54 - 1,251.02 = 14,936.52.
- "Ancillary Per Cap $8.08" equals 14,936.52 / 1,849 attendance = 8.08. Without subtracting Bar it would be 8.75.
- "24.6% vs prior period" equals 14,936.52 / (13,766.83 - 1,783.60) - 1 = 24.6%, using prior week 2026-09-21 to 09-27 with Bar removed the same way. Without that it would be 17.6%.

See Power BI cross-checks above.

Unexplained. "Avg Check $38.40" and "Ancillary Capture Rate 31.8%". We have 484 Summit-week orders. Net/orders is 33.45 and final_total/orders is 37.83. 484 / 1,849 = 26.2%. Neither matches, and the denominators those measures use are unknown.

#### Open questions

Bar and the gaps are settled by D-003, D-005 and D-007. The Ancillary
visual question is open in PROGRESS.md.

### Profile: private events, labor, reference workbooks

Free-text columns (`comments`, `lost_reason_name`) were profiled for
null counts and lengths only.

#### 03_Private_Events.xlsx / private_events

README says booking_grand_total repeats on each event row of a multi-day booking.

- Rows: 1,030 (459 EVENT, 571 LEAD).
- Keys: `event_id` unique over 459 non-null. `lead_id` 996 distinct over 1,030 rows,
  `booking_id` 425 distinct over 459, because 34 bookings have two event rows
  (68 rows). No booking has mixed status or mixed booking_grand_total.
- Nulls: every event-level column (event_id, booking_id, event_date, event_start_time,
  guaranteed_guest_count, rooms, F&B, price, rental, admin, grand_total, deposit,
  amount_due, booking_grand_total) is null on exactly the 571 LEAD rows.
  booking_definite_date null 649, booking_lost_date null 971, lost_reason_name null 672.
- Free text: lost_reason_name 358 non-null (59 Lost events + 299 leads), length 6 to 25.
- record_type: LEAD 571, EVENT 459.
- booking_status: Lead 571, Definite 358, Lost 59, Canceled 23, Tentative 19.
  Lead only on LEAD rows, the other four only on EVENT rows.
- venue_code: SSD 545, RTL 267, TRO 218. location_name is clean (3 values, 1:1 with code).
- booking_market_segment: Corporate 396, Social 251, Holiday Party 155, Wedding 96,
  Nonprofit 67, Photoshoot 65. rooms: Observation Level + Lounge 253, Full Venue Buyout 206.
  selected_lead_sources: 6 clean values. owner_id: S-201, S-202, S-211, S-221, S-222.
- Dates: event_date 2025-01-03 to 2027-02-07. booking_definite_date 2024-11-13 to
  2026-10-17 (after "today" 2026-10-05, see open questions). booking_lost_date
  2024-12-26 to 2026-08-10. created_at / lead_created_date 2024-11-02 to 2026-10-04.
- Alternate spellings: none in this sheet.
- Money identities: grand_total = F&B + rental + admin on 459/459. F&B = guest_count x
  price_per_person on 459/459 (not guaranteed count). deposit + amount_due = grand_total
  on 410. The 23 Canceled rows have amount_due 0, and the other 26 are off by one cent.
- booking_definite_date is set on Definite (358) and Canceled (23) rows, never on
  Tentative or Lost. booking_lost_date and lost_reason_name only on Lost (59).

#### 04_Labor.xlsx / labor_actual

README says actuals run through 2026-10-04 and department labels are raw on purpose.

- Rows: 16,512. Dates 2025-01-01 to 2026-10-04. actual_out runs to 2026-10-05 06:00.
- Keys: (venue_code, person_id, date, actual_in) has 16,511 distinct values. The one
  duplicate pair is one SSD employee on 2026-01-06, in at 11:00. One row is out 17:00, 6.0 h,
  rate 15.85, $95.10. The other is out 16:00, 4.5 h, rate 15.00, $67.50. They are not
  identical. (person_id, date) is not a key: 480 rows share a person-day.
- Nulls: sched_in/sched_out 1,137 (all are the rows with a comment, 17 chars each,
  unscheduled shifts). rate and reg/ot/total_earnings 132 (the same rows). comments
  15,375 null, 1,137 non-null.
- venue_code: SSD 7,001, RTL 4,980, TRO 4,531. paygroup_id is 1:1 (PG-DEN, PG-NSH, PG-PIT).
- location_name has 12 variants (case and trailing space) that normalise to 3. Each
  maps to its own venue_code with no conflicts.
- working_dept has 24 raw labels, mapped below. position has 18 clean values.
- rate_type is always Hourly. dt_hrs is always 0. is_late is N 15,115 and Y 1,397.
  pay_period_flag is Previous 16,337 and Current 175 (Current = exactly 2026-09-28 to
  2026-10-04).

#### 04_Labor.xlsx / labor_schedule

- Rows: 16,450, schedule_date 2025-01-01 to 2026-10-18.
- Keys: (person_id, schedule_date) unique. No nulls. No exact duplicates.
- venue_code: SSD 7,078, RTL 4,920, TRO 4,452. location_name has the same 12 variants.
  department has the same 24 raw labels. position has the same 18 values.

#### 05_Reference_Budget_Context.xlsx

- dim_venue: 3 rows, no nulls. SSD Denver America/Denver L-1001, RTL Nashville
  America/Chicago L-1002, TRO Pittsburgh America/New_York L-1003. attraction_prefix
  equals venue_code. Timezones are valid IANA names and match the cities.
- budget_daily: 10,950 rows = 3 venues x 730 days (2025-01-01 to 2026-12-31) x 5
  departments (Ticket, Restaurant, Cafe, Merchandise, Private Events). Key
  (venue, date, department) unique. budget_attendance is set only on Ticket rows
  (2,190), null on the other 8,760. No zero or negative budgets. There is no Bar
  department in the budget, so actual Bar revenue has no plan line of its own.
- weather_cached: 1,926 rows = 3 x 642 days (2025-01-01 to 2026-10-04). Key unique,
  no nulls. Ranges look plausible (temp_max 8.2 to 103.6 F, temp_min -15.0 to 78.7 F,
  snow up to 8.24 in). 13 distinct WMO codes, all valid (0-3, 51-55, 61-65, 71-75).
  There is nothing after 2026-10-04, so it cannot serve as a forecast fallback.
- market_events_seed: 72 rows (SSD 28, RTL 22, TRO 22). event_id unique, no nulls,
  no end < start. Categories: Sports 44, Festival 18, Convention 8, Parade 2. Dates
  2025-04-03 to 2026-12-07, 18 start on or after 2026-10-05.

#### H7 messy labels: CONFIRMED (fully mappable)

Department mapping. It is the same for labor_actual.working_dept and
labor_schedule.department. Match after strip and lower-case.

| raw variants | canonical |
|---|---|
| Operations, OPS, operations␠, Guest Services-Ops | Operations |
| Restaurant, F&B - Restaurant, FNB Rest, Food & Beverage | Restaurant |
| Kitchen, KITCHEN, Back of House, BOH | Kitchen |
| Cafe, CAFE, Cafe␠, F&B - Cafe | Cafe |
| Merchandise, MERCH, Gift Shop, Retail | Merchandise |
| Support, SUPPORT, Security & Support, Facilities/Support | Support |

"Food & Beverage" is the only ambiguous label. All 679 actual rows hold Host,
Server, Busser or Bartender, the positions the restaurant labels hold. No Barista or
Cashier (cafe) rows carry it, so it maps to Restaurant. Every position maps to one
canonical department (no position spans two), so position can serve as a
cross-check. The six canonical names are the six departments on the Power BI Labor
page. Unmapped rows: 0. location_name variants map to the venue name for their
venue_code (summit sky deck, SUMMIT SKY DECK, "Summit Sky Deck " -> Summit Sky Deck,
and the same for the other two). venue_code and position need no mapping.

The mapping changes only the department split, not Summit-week totals. With this
mapping the SSD department hours (184.0 / 77.4 / 92.7 / 54.7 / 39.2 / 36.4) round to
the Power BI table (184 / 77 / 93 / 55 / 39 / 36). The $/hr values differ by 0.01 to
0.03 (for example Kitchen 20.96 vs 20.94, Merch 19.42 vs 19.45). That gap is unexplained.

#### H8 labor rules: PARTIAL

- Overnight: CONFIRMED that `date` is always the start date. There are 639 overnight
  shifts and date equals the actual_in date on all 16,512 rows. SSD has 3 overnight
  shifts in the week (one on 09-29, two on 10-03), none crossing a week
  boundary, so attribution does not move SSD hours. It does matter for TRO. Start-date
  attribution gives 321.17 h (target 321.2). End-date gives 313.70.
- Hours columns: total_hrs = reg_hrs + ot_hrs on every row. Clock time
  (actual_out - actual_in) minus total_hrs is 0 on 4,508 rows and 0.5 h on 12,004
  rows. The 0.5 h is deducted when the clock span is over 6 h (10,867 rows) or the
  shift is unscheduled (1,137 rows, all 5.0 h clock and 4.5 h paid). This looks like
  an unpaid meal break. The deduction stands (D-006).
- OT: reg_hrs never exceeds 8 (888 OT rows). ot_earnings = 1.5 x rate x ot_hrs (884
  rows, the rest rounding). reg_earnings = reg_hrs x rate on every rated row.
- Missing rates: 132 rows (SSD 59, RTL 42, TRO 31) have rate and all three earnings
  columns null while hours are present (807.47 h). Every one of those people has a
  rate on other shifts, but rate varies on almost every shift (123 of 123 people have
  more than one rate, one person has 123 distinct rates between 17.03 and
  22.42). So a fill from the same person, the same position or the schedule (which has
  no rate column) is an estimate, not a recovery. In the week: SSD 2 rows (a Prep
  Cook on 10-02, 5.48 h, and a Ticket Taker on 10-03, 7.50 h, 12.98 h), TRO 1 row (4.30 h),
  RTL 0.
- Tips: 4,412 rows, $87,964 total. SSD week tips $513.86. Excluding tips is needed to
  match.
- Duplicates: no exact duplicates. There is 1 business-key duplicate (SSD
  2026-01-06, above, outside the week). Also, 237 shifts overlap the same person's
  previous shift, 174 of them unscheduled "cover" rows. In the SSD week 2 overlapping
  shifts carry 11.0 h. Power BI evidently counts them, because the targets only match
  with them included. They count (D-006).

#### H9 private events: CONFIRMED

The status vocabulary is Definite, Tentative, Lost, Canceled (EVENT rows) and Lead
(LEAD rows). 34 two-day bookings repeat booking_grand_total on both rows. In all 425
bookings booking_grand_total equals the sum of the event grand_totals. Summing
booking_grand_total over event rows overstates by $736,246.60 across the file. In
the reconciliation week every event is a single-day Definite booking, so every rule
variant gives the same number. Summit impact: none in this week, since the week has
1 event (EV-000222 / BK-000208, 2026-10-02, $6,565).

#### H10 missing venue-days: REJECTED for these feeds

labor_actual, labor_schedule, budget_daily (all 5 departments) and weather_cached
have 0 missing venue-days over their full ranges. The Nashville April day is not a
gap in labor. The lowest RTL April labor day is 2026-04-27 with 5 shifts (median 8,
minimum over all days 4), which is within the normal range. The gap must be in the
ticketing or POS feeds (out of this scope). Private events have no daily
expectation. Summit-week impact: none.

#### H11 other: PARTIAL

- Budget has no Bar department, and budget_attendance sits only on Ticket rows.
- Weather ends 2026-10-04, so it has no forward days.
- booking_definite_date goes up to 2026-10-17, after today (2026-10-05). An
  as-of-today view would have to ignore those dates. Count unexplained, see the
  questions below.
- dim_venue is clean. Timezones are valid.
- pay_period_flag = Current marks exactly the reconciliation week.

#### Reproduction (2026-09-28 to 2026-10-04)

| venue | rule | hours | payroll | PE |
|---|---|---|---|---|
| SSD | start date, sum total_hrs, sum total_earnings (null-rate rows add 0), no tips | 484.47 -> 484.5 match | 9,346.69 -> 9,347 match | 6,565.00 match |
| SSD | end-date attribution | 484.47 | 9,346.69 | |
| SSD | clock hours | 512.48 miss | | |
| SSD | per-shift total_hrs rounded to 0.1 | 484.90 | | |
| SSD | rated rows only | 471.49 miss | | |
| SSD | scheduled rows only | 470.97 miss | | |
| SSD | reg + 1.5 x ot recomputed | | 9,346.71 | |
| SSD | plus tips | | 9,860.55 miss | |
| SSD | fill missing rates with person median | | 9,613.65 miss | |
| RTL | start date | 358.69 match | 6,942.10 match | 26,324.82 -> 26,325 match |
| TRO | start date | 321.17 match | 6,257.93 match | 17,564.55 -> 17,565 match |
| TRO | end date | 313.70 miss | | |
| TRO | fill missing rate | | 6,341.44 miss | |

Private events for all venues: Definite, event-level grand_total on event_date. In
this week every alternative (all statuses, Definite + Tentative, booking-level)
gives the same number, so the week cannot tell the rules apart. Prior week SSD
Definite is $22,256 (EV-000220 and EV-000221, one two-day booking at $11,128 per
day). 6,565 / 22,256 = -70.5%, which matches the Power BI "▼70.5% vs prior period".
Booking-level money would give 2 x 22,256, so this fits event-level money.

All 8 Power BI targets in this scope match for all 3 venues under one rule set. The
targets include the 2 SSD missing-rate shifts at $0 payroll (12.98 h are counted in
hours) and the 2 overlapping shifts (11.0 h).

#### Cross-checks

See Power BI cross-checks above.

#### Open questions

- "Event Count 4" on the SSD Private Events card: only 1 event of any status falls in
  the week. 4 equals the Definite SSD events in calendar October 2026 (EV-000222, 223,
  225, 226), but that may be a coincidence. Unexplained.
- booking_definite_date after 2026-10-05: is the CRM export later than "today"?

