import { useEffect, useMemo, useRef, useState } from "react";

import { getTeamLogo } from "../utils/teamLogos";

import "./SportsSelect.css";

// ============================================================
// NOMBRES VISUALES
//
// IMPORTANTE:
//
// El valor REAL sigue siendo el que existe en el histórico.
//
// Ejemplo:
//
// Valor interno:
// Mazatlán
//
// Valor mostrado:
// Atlante
// ============================================================

const TEAM_DISPLAY_NAMES = {
  Mazatlán: "Atlante",
};

const getDisplayName = (option) => {
  return TEAM_DISPLAY_NAMES[option] || option;
};

function SportsSelect({
  label,
  value,
  options = [],
  placeholder = "Seleccionar...",
  searchPlaceholder = "Buscar...",
  onChange,
  disabledValues = [],
  loading = false,
  disabled = false,
  variant = "green",
  badge,
  showTeamLogo = false,
}) {
  const [open, setOpen] = useState(false);

  const [search, setSearch] = useState("");

  const containerRef = useRef(null);

  // ============================================================
  // VALORES BLOQUEADOS
  // ============================================================

  const disabledSet = useMemo(() => {
    return new Set(
      disabledValues
        .filter(Boolean)
        .map((item) => String(item).trim().toLocaleLowerCase("es-MX")),
    );
  }, [disabledValues]);

  // ============================================================
  // FILTRAR
  //
  // Permite buscar tanto por:
  //
  // Mazatlán
  // Atlante
  //
  // pero conserva internamente:
  //
  // Mazatlán
  // ============================================================

  const filteredOptions = useMemo(() => {
    const term = search.trim().toLocaleLowerCase("es-MX");

    if (!term) {
      return options;
    }

    return options.filter((option) => {
      const realName = String(option).toLocaleLowerCase("es-MX");

      const displayName = String(getDisplayName(option)).toLocaleLowerCase(
        "es-MX",
      );

      return realName.includes(term) || displayName.includes(term);
    });
  }, [options, search]);

  // ============================================================
  // LOGO DEL VALOR SELECCIONADO
  //
  // Se conserva el valor REAL.
  // ============================================================

  const selectedLogo = useMemo(() => {
    if (!showTeamLogo || !value) {
      return null;
    }

    return getTeamLogo(value);
  }, [value, showTeamLogo]);

  // ============================================================
  // CLICK FUERA
  // ============================================================

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target)
      ) {
        setOpen(false);

        setSearch("");
      }
    };

    document.addEventListener("mousedown", handleClickOutside);

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  // ============================================================
  // ESC
  // ============================================================

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        setOpen(false);

        setSearch("");
      }
    };

    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  // ============================================================
  // SELECCIONAR
  //
  // IMPORTANTE:
  //
  // Si visualmente aparece Atlante:
  //
  // option sigue siendo "Mazatlán".
  //
  // Por lo tanto:
  //
  // onChange("Mazatlán")
  // ============================================================

  const seleccionar = (option) => {
    const normalizado = String(option).trim().toLocaleLowerCase("es-MX");

    if (disabledSet.has(normalizado)) {
      return;
    }

    onChange?.(option);

    setOpen(false);

    setSearch("");
  };

  // ============================================================
  // ABRIR / CERRAR
  // ============================================================

  const toggle = () => {
    if (disabled || loading) {
      return;
    }

    setOpen((prev) => !prev);
  };

  // ============================================================
  // RENDER
  // ============================================================

  return (
    <div
      ref={containerRef}
      className={`sports-select sports-select--${variant} ${
        open ? "sports-select--open" : ""
      }`}
    >
      {/* ================================================= */}
      {/* LABEL */}
      {/* ================================================= */}

      <div className="sports-select__label-row">
        <span className="sports-select__label">{label}</span>

        {badge && <span className="sports-select__badge">{badge}</span>}
      </div>

      {/* ================================================= */}
      {/* CONTROL */}
      {/* ================================================= */}

      <button
        type="button"
        className="sports-select__control"
        onClick={toggle}
        disabled={disabled || loading}
      >
        {/* =============================================== */}
        {/* LOGO / ICONO */}
        {/* =============================================== */}

        {showTeamLogo ? (
          <span className="sports-select__team-logo-wrapper">
            {selectedLogo ? (
              <img
                src={selectedLogo}
                alt={value ? getDisplayName(value) : ""}
                className="sports-select__team-logo"
              />
            ) : (
              <span
                className={`sports-select__accent sports-select__accent--placeholder ${
                  variant === "cyan" ? "sports-select__accent--cyan" : ""
                }`}
              >
                {variant === "green" ? "L" : "V"}
              </span>
            )}
          </span>
        ) : (
          <span className="sports-select__accent">A</span>
        )}

        {/* =============================================== */}
        {/* VALUE */}
        {/* =============================================== */}

        <span
          className={`sports-select__value ${
            !value ? "sports-select__value--placeholder" : ""
          }`}
        >
          {loading
            ? "Cargando catálogo..."
            : value
              ? getDisplayName(value)
              : placeholder}
        </span>

        {/* =============================================== */}
        {/* CHEVRON */}
        {/* =============================================== */}

        {loading ? (
          <span className="sports-select__loader" />
        ) : (
          <span
            className={`sports-select__chevron ${
              open ? "sports-select__chevron--open" : ""
            }`}
          >
            ↓
          </span>
        )}
      </button>

      {/* ================================================= */}
      {/* DROPDOWN */}
      {/* ================================================= */}

      {open && (
        <div className="sports-select__dropdown">
          {/* =============================================== */}
          {/* SEARCH */}
          {/* =============================================== */}

          <div className="sports-select__search-wrapper">
            <span>⌕</span>

            <input
              type="text"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={searchPlaceholder}
              autoFocus
            />
          </div>

          {/* =============================================== */}
          {/* META */}
          {/* =============================================== */}

          <div className="sports-select__dropdown-meta">
            <span>{filteredOptions.length} opciones</span>

            {value && (
              <button
                type="button"
                onClick={() => {
                  onChange?.("");

                  setOpen(false);

                  setSearch("");
                }}
              >
                Limpiar
              </button>
            )}
          </div>

          {/* =============================================== */}
          {/* OPTIONS */}
          {/* =============================================== */}

          <div className="sports-select__options">
            {filteredOptions.length === 0 ? (
              <div className="sports-select__empty">
                No se encontraron resultados
              </div>
            ) : (
              filteredOptions.map((option) => {
                const optionKey = String(option);

                const selected = optionKey === value;

                const optionDisabled = disabledSet.has(
                  optionKey.trim().toLocaleLowerCase("es-MX"),
                );

                const teamLogo = showTeamLogo ? getTeamLogo(option) : null;

                return (
                  <button
                    type="button"
                    key={optionKey}
                    disabled={optionDisabled}
                    className={`sports-select__option ${
                      selected ? "sports-select__option--selected" : ""
                    } ${
                      optionDisabled ? "sports-select__option--disabled" : ""
                    }`}
                    onClick={() => seleccionar(option)}
                  >
                    {/* ================================= */}
                    {/* LOGO / CHECK */}
                    {/* ================================= */}

                    {showTeamLogo ? (
                      <span className="sports-select__option-logo-wrapper">
                        {teamLogo ? (
                          <img
                            src={teamLogo}
                            alt=""
                            className="sports-select__option-logo"
                          />
                        ) : (
                          <span className="sports-select__option-logo-fallback">
                            {getDisplayName(option)}
                          </span>
                        )}
                      </span>
                    ) : (
                      <span className="sports-select__option-icon">
                        {selected ? "✓" : ""}
                      </span>
                    )}

                    {/* ================================= */}
                    {/* NAME */}
                    {/* ================================= */}

                    <span className="sports-select__option-name">
                      {getDisplayName(option)}
                    </span>

                    {/* ================================= */}
                    {/* SELECTED */}
                    {/* ================================= */}

                    {selected && !optionDisabled && (
                      <span className="sports-select__selected-indicator">
                        ✓
                      </span>
                    )}

                    {/* ================================= */}
                    {/* DISABLED */}
                    {/* ================================= */}

                    {optionDisabled && (
                      <span className="sports-select__option-disabled-label">
                        Ya seleccionado
                      </span>
                    )}
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default SportsSelect;
