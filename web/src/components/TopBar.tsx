import logoBlack from "@brand/logos/logo-horizontal-black.png";
import logoWhite from "@brand/logos/logo-horizontal-white.png";
import { Link, useLocation } from "react-router-dom";
import type { Theme } from "../theme";

interface Props {
  theme: Theme;
  onToggleTheme: () => void;
  userName: string | null;
  onMenu: () => void;
}

export function TopBar({ theme, onToggleTheme, userName, onMenu }: Props) {
  const { search } = useLocation();
  return (
    <header className="topbar">
      <button className="menu-button" aria-label="Open menu" onClick={onMenu}>
        ☰
      </button>
      <img
        className="logo"
        src={theme === "dark" ? logoWhite : logoBlack}
        alt="Legends Global"
      />
      <span className="app-name">Attractions</span>
      <span className="spacer" />
      <Link to={{ pathname: "/support", search }} className="btn" aria-label="Help & Support">
        ? <span className="help-label">Help &amp; Support</span>
      </Link>
      <button onClick={onToggleTheme} aria-label="Toggle light and dark mode">
        {theme === "dark" ? "☀ Light" : "☾ Dark"}
      </button>
      <span className="user" data-testid="user">
        {userName ?? ""}
      </span>
    </header>
  );
}
