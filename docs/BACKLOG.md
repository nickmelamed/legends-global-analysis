# Backlog

Work we chose not to do yet, with the reason.

- docker-compose and the Dockerfiles for load, api and web. Planned for
  Phase 6, next to the README.
- Upgrade to Vite 6.4.3 or later and React Router 7 to clear the dev-only
  audit findings (D-014).
- Content for Ticketing, F&B, Merchandise, Events, Pacing Report, Cost
  Watch, Support and Settings. They are placeholders that keep the filters.
- A dev user switcher in the UI. Today `DEV_USER` or the `X-Dev-User`
  header picks the user, so showing `marcus@dev` needs a restart.
- Entra ID sign-in through Easy Auth's `X-MS-CLIENT-PRINCIPAL` header.
- The trend's Day/Week/Month choice is page state, not a URL param, so it
  is not deep-linkable.
