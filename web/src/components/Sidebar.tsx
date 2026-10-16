import { NavLink, useLocation } from "react-router-dom";
import type { Filters } from "../api";
import { FilterPanel } from "./FilterPanel";

export const PAGES = [
  { path: "/overview", label: "Overview" },
  { path: "/ticketing", label: "Ticketing" },
  { path: "/fnb", label: "F&B" },
  { path: "/merchandise", label: "Merchandise" },
  { path: "/events", label: "Events" },
  { path: "/pacing", label: "Pacing Report" },
  { path: "/cost-watch", label: "Cost Watch" },
  { path: "/ask", label: "Ask the data" },
];
export const FOOTER_PAGES = [
  { path: "/support", label: "Support" },
  { path: "/settings", label: "Settings" },
];

interface Props {
  open: boolean;
  onNavigate: () => void;
  options: Filters | null;
}

export function Sidebar({ open, onNavigate, options }: Props) {
  // Tab links carry the query string so the filters follow the user.
  const { search } = useLocation();
  const link = (p: { path: string; label: string }) => (
    <NavLink key={p.path} to={{ pathname: p.path, search }} onClick={onNavigate}>
      {p.label}
    </NavLink>
  );
  return (
    <aside className={`sidebar${open ? " open" : ""}`} aria-label="Navigation and filters">
      <nav className="nav">
        {PAGES.map(link)}
        <hr />
        {FOOTER_PAGES.map(link)}
      </nav>
      <FilterPanel options={options} />
    </aside>
  );
}
