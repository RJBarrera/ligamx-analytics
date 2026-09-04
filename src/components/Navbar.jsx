import { useState } from "react";

import "./Navbar.css";

const NAV_ITEMS = [
  {
    label: "Inicio",
    href: "#inicio",
  },
  {
    label: "Predicción",
    href: "#prediccion",
  },
  {
    label: "Analítica",
    href: "#analitica",
  },
  {
    label: "Modelo",
    href: "#modelo",
  },
];

function Navbar() {
  const [menuOpen, setMenuOpen] = useState(false);

  const cerrarMenu = () => {
    setMenuOpen(false);
  };

  return (
    <header className="sports-navbar">
      <div className="sports-navbar__inner">
        {/* ================================================= */}
        {/* BRAND */}
        {/* ================================================= */}

        <a href="/" className="sports-navbar__brand" onClick={cerrarMenu}>
          <div className="sports-navbar__logo">
            <svg viewBox="0 0 40 40" aria-hidden="true">
              <path
                d="M7 29.5V23l7-7 5 5 9-10 5 4.5V30"
                fill="none"
                stroke="currentColor"
                strokeWidth="3"
                strokeLinecap="round"
                strokeLinejoin="round"
              />

              <path
                d="M7 32.5h26"
                fill="none"
                stroke="currentColor"
                strokeWidth="3"
                strokeLinecap="round"
              />

              <circle cx="28" cy="11" r="3" fill="currentColor" />
            </svg>
          </div>

          <div className="sports-navbar__brand-text">
            <strong>
              Stat
              <span>MX</span>
            </strong>

            <div className="glob-sports-navbar__engine-dot">
              <span className="sports-navbar__engine-dot" />
              <small>Análisis de la Liga MX</small>
            </div>
          </div>
        </a>

        {/* ================================================= */}
        {/* DESKTOP NAV */}
        {/* ================================================= */}

        <nav className="sports-navbar__links">
          {NAV_ITEMS.map((item) => (
            <a key={item.label} href={item.href}>
              {item.label}
            </a>
          ))}
          <a href="#en-vivo" className="navbar-live-link">
            <span className="navbar-live-dot" />
            En Vivo
            <small>LIVE</small>
          </a>
        </nav>

        {/* ================================================= */}
        {/* RIGHT */}
        {/* ================================================= */}

        <div className="sports-navbar__actions">
          <a href="/" className="sports-navbar__cta">
            Nueva predicción
            <span>→</span>
          </a>

          <button
            type="button"
            className={`sports-navbar__menu-button ${
              menuOpen ? "sports-navbar__menu-button--open" : ""
            }`}
            aria-label="Abrir menú"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((prev) => !prev)}
          >
            <span />
            <span />
            <span />
          </button>
        </div>
      </div>

      {/* ================================================= */}
      {/* MOBILE MENU */}
      {/* ================================================= */}

      <div
        className={`sports-navbar__mobile ${
          menuOpen ? "sports-navbar__mobile--open" : ""
        }`}
      >
        <nav>
          {NAV_ITEMS.map((item) => (
            <a key={item.label} href={item.href} onClick={cerrarMenu}>
              <span>{item.label}</span>

              <strong>→</strong>
            </a>
          ))}
        </nav>

        <div className="sports-navbar__mobile-engine">
          <span className="sports-navbar__engine-dot" />
          Motor estadístico disponible
        </div>
      </div>
    </header>
  );
}

export default Navbar;
