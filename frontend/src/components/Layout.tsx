import { Link, useLocation } from "react-router-dom";

export function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation();

  const navLinks = [
    { to: "/", label: "Playground" },
    { to: "/history", label: "History" },
  ];

  return (
    <div className="app-layout">
      <header className="app-header">
        <h1>LLM Router</h1>
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
      </header>
      <main className="app-main">{children}</main>
    </div>
  );
}
