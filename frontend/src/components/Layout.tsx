import { Link, useLocation } from "react-router-dom";
import { useTheme, type Theme } from "../hooks/useTheme";

const THEMES: { value: Theme; label: string }[] = [
  { value: "dark", label: "Dark" },
  { value: "light", label: "Light" },
  { value: "blue", label: "Blue" },
];

export function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const { theme, setTheme } = useTheme();

  const navLinks = [
    { to: "/", label: "Playground" },
    { to: "/querylab", label: "QueryLab" },
    { to: "/history", label: "History" },
  ];

  return (
    <div className="app-layout">
      <header className="app-header">
        <h1>LLM Router</h1>
        <div className="flex items-center">
          <nav>
            {navLinks.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                className={`nav-link ${location.pathname === link.to ? "active" : ""}`}
              >
                {link.label}
              </Link>
            ))}
          </nav>
          <div className="theme-selector">
            {THEMES.map((t) => (
              <button
                key={t.value}
                className={`theme-btn theme-btn--${t.value} ${theme === t.value ? "active" : ""}`}
                onClick={() => setTheme(t.value)}
                title={t.label}
                aria-label={`${t.label} theme`}
              />
            ))}
          </div>
        </div>
      </header>
      <main className="app-main">{children}</main>
    </div>
  );
}
