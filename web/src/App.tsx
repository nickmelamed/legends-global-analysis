import { useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import type { Filters, Freshness } from "./api";
import { FreshnessFooter } from "./components/FreshnessFooter";
import { FOOTER_PAGES, PAGES, Sidebar } from "./components/Sidebar";
import { TopBar } from "./components/TopBar";
import { useFilters } from "./filters";
import { Ask } from "./pages/Ask";
import { Overview } from "./pages/Overview";
import { Placeholder } from "./pages/Placeholder";
import { useTheme } from "./theme";
import { useApi } from "./useApi";

export function App() {
  const [theme, toggleTheme] = useTheme();
  const [drawer, setDrawer] = useState(false);
  const { search } = useLocation();
  const { query } = useFilters();
  const options = useApi<Filters>(`/api/filters?${query}`);
  const fresh = useApi<Freshness>(`/api/freshness?${query}`);
  const opts = options.state === "ok" ? options.data : null;
  useEffect(() => {
    if (!drawer) return;
    const close = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      setDrawer(false);
      // Focus was inside the drawer, which is now hidden, so hand it back to
      // the button that opened it.
      document.querySelector<HTMLButtonElement>(".menu-button")?.focus();
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [drawer]);
  return (
    <div className="app">
      <TopBar
        theme={theme}
        onToggleTheme={toggleTheme}
        userName={opts?.user.display_name ?? null}
        onMenu={() => setDrawer(!drawer)}
      />
      <div className="body">
        <Sidebar open={drawer} onNavigate={() => setDrawer(false)} options={opts} />
        {drawer && <div className="scrim" onClick={() => setDrawer(false)} />}
        <main>
          <Routes>
            <Route path="/" element={<Navigate to={{ pathname: "/overview", search }} replace />} />
            <Route path="/overview" element={<Overview theme={theme} />} />
            <Route path="/ask" element={<Ask />} />
            {[...PAGES, ...FOOTER_PAGES]
              .filter((p) => p.path !== "/overview" && p.path !== "/ask")
              .map((p) => (
                <Route key={p.path} path={p.path} element={<Placeholder title={p.label} />} />
              ))}
            <Route path="*" element={<Placeholder title="Not found" />} />
          </Routes>
          <FreshnessFooter fresh={fresh} />
        </main>
      </div>
    </div>
  );
}
