# Stakeholder backlog

The four stakeholders have fewer distinct needs than asks. Dana and Marcus
both want to know what kind of day is coming. Priya and Ben both want
numbers they can trust and trace. Marcus also wants questions answered in
plain words, which the Ask prototype tests.

## Asks and needs

| Who, and when they use it | Asked for | Needs |
|---|---|---|
| Dana, Sales, Monday review and weekly planning | Weather, local events weeks ahead, competitor prices, all venues visible | An explanation next to a swing in the numbers, and early warning of busy dates so packages go out in time. Portfolio-wide revenue for group sales. A private events conversion figure she can trust. |
| Marcus, Summit GM, before the doors open and when scheduling two weeks out | A 5 AM text, a staffing forecast, overtime flags, typed questions | A staffing call he can make in thirty seconds, with an honest range. Overtime caught during the week, before payroll closes. A page that loads on a phone. |
| Priya, Finance, month end and every reconciliation | Row-level trace, a load report, year-over-year by class, pace by department, exports with filters | Proof that a number is right, or the rows that show why it is not. Missing days shown as missing. |
| Ben, IT and Security, before go-live and at 2 AM | Entra, server-side scope, no secrets, no guest data to AI, a known AI cost, licensed feeds | Something his small team can run and audit. |

## Where they conflict

Dana wants every salesperson to see every venue. Ben wants venue access
enforced by the server. These fit together if scope is assigned by role. The API already resolves each user to a list of venues and applies
it in one helper, so a "portfolio sales" Entra group can map to all venues
while a GM maps to one. The open part is whether sales should also see
labor and payroll for venues they do not run. I would scope by venue and by
metric family, and default sales to revenue only.

Marcus wants speed and Priya wants accuracy. A 5 AM summary has to read
yesterday's data before anyone has checked it. The way through is to run
the load overnight, publish only when every blocking check passes, and say
"no data" or "stale since" when it fails. 

Automation versus trust shows up twice. Marcus wants the forecast to tell
him which shifts to cut, but guaranteed hours and minimum-shift rules mean a
person decides. Dana wants prices pulled automatically. Both features should
recommend, show the evidence and leave the action to a person.

## What to build first

1. A load health page for Priya. The `data_quality` table already records
   every check on every run (duplicates dropped, missing rates, missing
   venue-days). The data is already there, so it is a small build.
2. An overtime flag for Marcus. Actual hours against the schedule, by
   week, checked daily. The labor and schedule sheets already have what it
   needs. Run daily, it would flag an overtime week before payroll closes.
3. Put the Overview, which already works on a phone, and the Ask prototype
   in front of Marcus and watch what he types.
4. Weather on the attendance chart from the cached sheet, to test whether
   weather explains the swings Dana asks about before paying for a forecast
   feed. Before trusting the sheet I would check where it came from, its
   units, whether a day is the local calendar day, and its licence. It ends
   on 2026-10-04 and holds observed weather only, so it cannot support a
   forecast. For production, the free Open-Meteo tier is non-commercial,
   which Ben has ruled out. A paid plan or another licensed provider is
   fine. The optional weather prototype was not built.

The day-ahead staffing forecast comes after these, once there is a backtest
that shows how often its range is right.

## What not to build

- Competitor price scraping. It likely breaks the competitors' terms of
  use, breaks whenever their sites change, and would feed pricing decisions
  with data nobody can vouch for. A licensed rate-shopping service or a
  weekly manual check is safer.
- Automatic shift changes, since guaranteed hours and minimum-shift rules
  need a person to decide.
- The private events conversion number, until its definition is agreed.
  Dana is not sure it is right and I have not checked it.

## Questions I would still ask

- Dana: what counts as a converted lead, and over what period? Which event
  sources does your rep's spreadsheet use? Does "all venues" include labor?
- Marcus: how far ahead is a forecast still useful, two weeks or two days?
  What range would you act on? Which shifts are guaranteed?
- Priya: which of your numbers disagree with the report, and by how much,
  so we can test the cancellation and cutover rules against them? Who signs
  off that the new numbers replace the old ones?
- Ben: is Azure OpenAI in our tenant required, or is the Anthropic API
  acceptable with zero data retention? What monthly AI budget is acceptable?
  Who owns the Entra groups?
- All: who should be told when a load fails, and how?

## How we would know it is used

Weekly active users by role, and whether Marcus opens it before 9 AM. Ask
questions per week and how often the answer falls back to a table.
Exports per user, which should fall if the screens answer the question.
For trust, count the data problems the load report caught before someone
asked about them. For Dana's "fewer surprises", count the weekly swings
over 10% that have no explanation attached.


