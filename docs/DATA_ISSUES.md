# Data issues

One entry per problem found in the supplied workbooks and how the load deals
with it. The workbooks are never edited. Every fix is a rule in
`pipeline/rules.py`, applied by `pipeline/load.py`, and the counts are
recorded in the `data_quality` table on every run. Impact is on the
reconciliation week (2026-09-28 to 2026-10-04) for Summit unless another venue
is named. Evidence is in docs/DATA_PROFILE.md under the hypothesis number.

| # | Issue | How it was detected | Fix | Rows affected | Week impact |
|---|---|---|---|---|---|
| 1 | Ticket lines loaded twice (H1) | `ticket_line_id` not unique. Pairs differ only in `ingestion_ts` | `dedup_ticket_loads` keeps the latest load. The blocking check `ticket_duplicate_loads_agree` stops the load if copies ever differ in anything else | 262 rows, all SSD 2026-06-06 and 06-07 (858 guests, $30,440.88) | None. Matters for June windows and next year's comparisons |
| 2 | Cancelled lines keep full quantity and value, and the two systems spell status differently (H2) | `record_status` is ACTIVE on every row, so only the status text marks a cancel | Per-source denylist in `TICKET_STATUS_CANCELLED`. An unknown status stops the load | 1,252 LT and 840 NT lines | 80 guests and $1,944.58 removed (11 lines) |
| 3 | Add-ons and private event entries sit in the ticket feed (H3) | `dim_package` classes NON-ADMISSION and EVENT carry quantity and, for add-ons, value | `NON_ADMISSION_CLASSES` excluded from attendance and ticket revenue | All add-on and event-entry lines (902 event entries) | 112 guests and $1,330.20 removed |
| 4 | NT `event_time` is UTC, LT is local (H6, H11) | Raw NT hours run 13 to 3. Converted from UTC they match `event_date` on every row | `ticket_business_dates` uses `event_date`, already the local date. The check `ticket_event_time_matches_event_date` converts `event_time` per source and warns if it leaves `event_date` (0 rows) | 34,411 NT rows | None. Using the raw UTC date would cost 1 guest and $160.23 |
| 5 | Sales after midnight belong to the previous business day | 431 POS rows before 04:00 local | `business_dates` applies the 4 AM cutoff after `to_local` | 431 rows | None at Summit. Moves one RTL Bar order ($14.50) into the week, which RTL F&B needs to match |
| 6 | POS order totals repeat on every line (H5) | One subtotal, tax, gratuity and total per order | Revenue is line-level net of discount, voids excluded. `pos_order_subtotal_matches_lines` is a blocking check | All 131,428 lines, 0 mismatched orders | Summing `final_total` per line instead would overstate Summit F&B and merch |
| 7 | POS rows that look like duplicates are real (H1) | 4,042 exact-copy rows. Subtotals only match with them kept | Never deduplicate POS rows | 4,042 rows | Dropping them would remove $417.56 |
| 8 | Labor department and location labels are messy (H7) | 24 department labels and 12 location spellings | `LABOR_DEPARTMENT` and `normalise_location`. Unmapped values stop the load. `labor_location_matches_venue` is blocking | 16,512 shifts relabelled, 0 unmapped | Department split only |
| 9 | Shifts with hours but no rate or earnings (H8) | Null `rate` and earnings on rows with `total_hrs` | Payroll stays null for those shifts and the window is marked incomplete. No estimate (D-006). Check `labor_missing_rate` | 132 shifts, 807.47 h | 2 shifts, 12.98 h without payroll, about $267 understated if shown as complete (D-006). TRO 1 shift, 4.30 h. A department-day where no shift has a rate stores null payroll, not $0 (67 department-days, none in the week) |
| 10 | Multi-day bookings repeat the booking total on each event (H9) | `booking_grand_total` equals the sum of event totals for all 425 bookings | Event-level `grand_total` on `event_date`, Definite only | 68 event rows in 34 bookings | None in the week. Booking-level money would overstate the file by $736,246.60 |
| 11 | Riverbend 2026-04-18 has no ticket or POS rows (H10) | `feed_coverage` gap with labor present that day | Shown as "no data", never zero (D-005). Check `venue_day_missing_from_feed` | 1 venue-day in 2 feeds | None |
| 12 | Bar has no rows on some days its venue traded (H10) | Outlet gaps on days with other POS rows | Bar shows a real $0 for that day (D-007) | RTL 26, TRO 67, SSD 2 days | None at Summit. RTL Bar has no rows on 10-02 |
| 13 | Overlapping shifts for the same person (H8) | 237 shifts start before the person's previous shift ends, 174 of them unscheduled covers | Counted, as Power BI does (D-006). Check `labor_overlapping_shifts` | 237 shifts | 2 shifts, 11.0 h, counted |
| 14 | One labor shift pair shares venue, person, date and clock-in (H8) | Business-key duplicate check | Both shifts are kept, since they differ in clock-out, hours and rate and neither is an exact copy. Check `labor_business_key_duplicates` | 1 pair, SSD 2026-01-06 | None |
