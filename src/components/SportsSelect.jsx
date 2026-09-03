import { useEffect, useMemo, useRef, useState } from "react";

import { getTeamLogo } from "../utils/teamLogos";

import "./SportsSelect.css";

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

  // Valores Bloqueados
  const disabledSet = useMemo(() => {
    return new Set(
      disabledValues
        .filter(Boolean)
        .map((item) => String(item).trim().toLocaleLowerCase("es-MX")),
    );
  }, [disabledValues]);

  // Filtrar
  const filteredOptions = useMemo(() => {
    const term = search.trim().toLocaleLowerCase("es-MX");

    const filtered = !term
      ? options
      : options.filter((option) =>
          String(option).toLocaleLowerCase("es-MX").includes(term),
        );

    return filtered.map((option) =>
      option === "Mazatlán" ? "Atlante" : option
    );
  }, [options, search]);

  // Logos del valor seleccionado
  const selectedLogo = useMemo(() => {
    if (!showTeamLogo || !value) {
      return null;
    }

    return getTeamLogo(value);
  }, [value, showTeamLogo]);

  // Click fuera
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

  // Esc
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

  // Seleccionar
  const seleccionar = (option) => {
    const normalizado = String(option).trim().toLocaleLowerCase("es-MX");

    if (disabledSet.has(normalizado)) {
      return;
    }

    onChange?.(option);
    setOpen(false);
    setSearch("");
  };

  // Abrir / Cerrar
  const toggle = () => {
    if (disabled || loading) {
      return;
    }

    setOpen((prev) => !prev);
  };

  // Render
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
                alt={value}
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
          {loading ? "Cargando catálogo..." : value || placeholder}
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
                            {String(option).charAt(0).toUpperCase()}
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

                    <span className="sports-select__option-name">{option}</span>

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
