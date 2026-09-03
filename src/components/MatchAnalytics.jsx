import axios from "axios";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { exportMatchReport } from "../utils/exportMatchReport";
import { getTeamLogo } from "../utils/teamLogos";
import ExportPdfButton from "./ExportPdfButton";
import "./MatchAnalytics.css";
import SportsSelect from "./SportsSelect";

const API_URL = "";
const COLORS = {
  local: "#21cfa1",
  draw: "#94a3b8",
  away: "#38bdf8",
  positive: "#22c55e",
  negative: "#dce3eb",
  corner: "#f59e0b",
  card: "#eab308",
};

// Utilidades
const porcentaje = (valor) => {
  return Number(valor || 0) * 100;
};

const numero = (valor, decimales = 2) => {
  const n = Number(valor);

  if (!Number.isFinite(n)) {
    return "0.00";
  }

  return n.toFixed(decimales);
};

// Iniciales del equipo cuando no hay logo
const obtenerInicialesEquipo = (nombre = "") => {
  const texto = String(nombre).trim();

  if (!texto) {
    return "?";
  }

  const palabras = texto
    .replace(/[.-]/g, " ")
    .split(/\s+/)
    .map((item) => item.trim())
    .filter(Boolean);

  if (palabras.length === 1) {
    return palabras[0].slice(0, 2).toUpperCase();
  }

  return `${palabras[0]?.[0] || ""}${palabras[1]?.[0] || ""}`.toUpperCase();
};

// ============================================================
// SELECCIONAR LA MAYOR PROBABILIDAD DE UN MERCADO
// ============================================================

const obtenerMayorProbabilidad = (categoria, opciones, descripcion = "") => {
  const validas = opciones
    .filter((opcion) => Number.isFinite(Number(opcion.probabilidad)))
    .map((opcion) => ({
      ...opcion,

      probabilidad: Number(opcion.probabilidad),
    }))
    .sort((a, b) => b.probabilidad - a.probabilidad);

  if (validas.length === 0) {
    return null;
  }

  return {
    categoria,

    descripcion,

    ...validas[0],
  };
};

// Barra de probabildad
function ProbabilityBar({ label, value, accent = "green" }) {
  const percent = Math.max(0, Math.min(100, porcentaje(value)));

  return (
    <div className="match-probability-row">
      <div className="match-probability-header">
        <span>{label}</span>

        <strong>{percent.toFixed(1)}%</strong>
      </div>

      <div className="match-probability-track">
        <div
          className={`match-probability-fill match-probability-fill--${accent}`}
          style={{
            width: `${percent}%`,
          }}
        />
      </div>
    </div>
  );
}

// Métrica
function MetricCard({ label, value, description, variant = "default", tag }) {
  return (
    <article className={`match-metric-card match-metric-card--${variant}`}>
      <div className="match-metric-card__top">
        <div className="match-metric-label">{label}</div>

        {tag && <span className="match-metric-tag">{tag}</span>}
      </div>

      <div className="match-metric-value">{value}</div>

      {description && (
        <div className="match-metric-description">{description}</div>
      )}
    </article>
  );
}

// Encabezado de sección
function SectionHeader({ code, eyebrow, title, description }) {
  return (
    <div className="match-section-heading">
      <div className="match-section-heading__code">{code}</div>

      <div>
        <span className="match-section-eyebrow">{eyebrow}</span>

        <h2>{title}</h2>

        {description && <p>{description}</p>}
      </div>
    </div>
  );
}

// Tooltip
function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) {
    return null;
  }

  return (
    <div className="match-chart-tooltip">
      {label && <div className="match-chart-tooltip-label">{label}</div>}

      {payload.map((item) => (
        <div
          key={`${item.name}-${item.value}`}
          className="match-chart-tooltip-value"
        >
          <span>{item.name}</span>

          <strong>{Number(item.value).toFixed(1)}%</strong>
        </div>
      ))}
    </div>
  );
}

// Componente Principal
function MatchAnalytics() {
  // Reporte PDF
  const reportRef = useRef(null);

  // Formulario
  const [form, setForm] = useState({
    local: "",
    visitante: "",
    arbitro: "",
  });

  // Catálogos
  const [catalogos, setCatalogos] = useState({
    equipos: [],
    arbitros: [],
  });
  const [loadingCatalogos, setLoadingCatalogos] = useState(true);
  const [errorCatalogos, setErrorCatalogos] = useState("");

  // Resultado
  const [resultado, setResultado] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // PDF
  const [exportingPdf, setExportingPdf] = useState(false);

  // Cargar Catálogos
  useEffect(() => {
    const cargarCatalogos = async () => {
      setLoadingCatalogos(true);

      setErrorCatalogos("");

      try {
        const { data } = await axios.get(`${API_URL}/api/catalogos`);

        if (!data?.success) {
          throw new Error("No fue posible cargar los catálogos.");
        }

        setCatalogos({
          equipos: Array.isArray(data.equipos) ? data.equipos : [],
          arbitros: Array.isArray(data.arbitros) ? data.arbitros : [],
        });
      } catch (requestError) {
        console.error("Error cargando catálogos:", requestError);

        setErrorCatalogos(
          requestError?.response?.data?.detail ||
            requestError?.message ||
            "No fue posible conectarse con Python.",
        );
      } finally {
        setLoadingCatalogos(false);
      }
    };

    cargarCatalogos();
  }, []);

  // Actualizar Campo
  const actualizarCampo = (campo, valor) => {
    setForm((prev) => ({
      ...prev,
      [campo]: valor,
    }));

    if (error) {
      setError("");
    }
  };

  // Analizar Partido
  const analizarPartido = async (event) => {
    event.preventDefault();

    const local = form.local.trim();
    const visitante = form.visitante.trim();
    const arbitro = form.arbitro.trim();

    // Validación
    if (!local || !visitante || !arbitro) {
      setError("Selecciona el equipo local, visitante y árbitro.");
      return;
    }

    if (
      local.toLocaleLowerCase("es-MX") === visitante.toLocaleLowerCase("es-MX")
    ) {
      setError("El equipo local y visitante deben ser diferentes.");
      return;
    }

    // Petición
    setLoading(true);
    setError("");

    try {
      const { data } = await axios.post(`${API_URL}/api/prediccion`, {
        local,
        visitante,
        arbitro,
      });

      if (!data?.success) {
        throw new Error(
          data?.message || "No fue posible calcular la predicción.",
        );
      }

      setResultado(data);

      // Scroll Resultados
      setTimeout(() => {
        document.getElementById("analitica")?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }, 150);
    } catch (requestError) {
      console.error("Error calculando predicción:", requestError);

      setResultado(null);

      setError(
        requestError?.response?.data?.detail ||
          requestError?.message ||
          "No fue posible comunicarse con el motor de predicción.",
      );
    } finally {
      setLoading(false);
    }
  };

  // Datos para gráficas
  const datosResultado = useMemo(() => {
    if (!resultado) {
      return null;
    }

    const goles = resultado.goles || {};
    const corners = resultado.corners || {};
    const tarjetas = resultado.tarjetas || {};

    // 1x2
    const resultado1X2 = [
      {
        name: resultado.partido?.local || "Local",
        value: porcentaje(goles?.["1X2"]?.Home),
        color: COLORS.local,
      },

      {
        name: "Empate",
        value: porcentaje(goles?.["1X2"]?.Draw),
        color: COLORS.draw,
      },

      {
        name: resultado.partido?.visitante || "Visitante",
        value: porcentaje(goles?.["1X2"]?.Away),
        color: COLORS.away,
      },
    ];

    // Marcadores
    const topMarcadores = Object.entries(goles?.Top_Scores || {}).map(
      ([marcador, probabilidad]) => ({
        marcador,
        probabilidad: porcentaje(probabilidad),
      }),
    );

    // BTTS
    const ambosAnotan = [
      {
        name: "Sí",
        value: porcentaje(goles?.BTTS?.Yes),
      },

      {
        name: "No",
        value: porcentaje(goles?.BTTS?.No),
      },
    ];

    // Córners Equipos
    const cornersEquipos = [
      {
        name: resultado.partido?.local || "Local",
        esperado: Number(corners?.expected_home || 0),
      },

      {
        name: resultado.partido?.visitante || "Visitante",
        esperado: Number(corners?.expected_away || 0),
      },
    ];

    // Escenario Dominante
    const ganador = [...resultado1X2].sort((a, b) => b.value - a.value)[0];

    return {
      goles,
      corners,
      tarjetas,

      resultado1X2,
      topMarcadores,
      ambosAnotan,
      cornersEquipos,
      ganador,
    };
  }, [resultado]);

  // ============================================================
  // RESUMEN DE MAYORES PROBABILIDADES
  // ============================================================

  const resumenProbabilidades = useMemo(() => {
    if (!resultado || !datosResultado) {
      return null;
    }

    const goles = datosResultado.goles || {};

    const corners = datosResultado.corners || {};

    const tarjetas = datosResultado.tarjetas || {};

    const candidatos = [];

    // ======================================================
    // 1X2
    // ======================================================

    candidatos.push(
      obtenerMayorProbabilidad(
        "Resultado 1X2",

        [
          {
            seleccion: `${resultado.partido.local} gana`,

            probabilidad: goles?.["1X2"]?.Home,

            tipo: "resultado",
          },

          {
            seleccion: "Empate",

            probabilidad: goles?.["1X2"]?.Draw,

            tipo: "resultado",
          },

          {
            seleccion: `${resultado.partido.visitante} gana`,

            probabilidad: goles?.["1X2"]?.Away,

            tipo: "resultado",
          },
        ],

        "Resultado final del partido",
      ),
    );

    // ======================================================
    // GOLES 1.5
    // ======================================================

    candidatos.push(
      obtenerMayorProbabilidad(
        "Total de goles 1.5",

        [
          {
            seleccion: "Más de 1.5 goles",

            probabilidad: goles?.Over_Under?.["Over 1.5"],

            tipo: "goles",
          },

          {
            seleccion: "Menos de 1.5 goles",

            probabilidad: goles?.Over_Under?.["Under 1.5"],

            tipo: "goles",
          },
        ],

        "Línea de goles del partido",
      ),
    );

    // ======================================================
    // GOLES 2.5
    // ======================================================

    candidatos.push(
      obtenerMayorProbabilidad(
        "Total de goles 2.5",

        [
          {
            seleccion: "Más de 2.5 goles",

            probabilidad: goles?.Over_Under?.["Over 2.5"],

            tipo: "goles",
          },

          {
            seleccion: "Menos de 2.5 goles",

            probabilidad: goles?.Over_Under?.["Under 2.5"],

            tipo: "goles",
          },
        ],

        "Línea principal de goles",
      ),
    );

    // ======================================================
    // BTTS
    // ======================================================

    candidatos.push(
      obtenerMayorProbabilidad(
        "Ambos equipos anotan",

        [
          {
            seleccion: "Sí anotan ambos",

            probabilidad: goles?.BTTS?.Yes,

            tipo: "goles",
          },

          {
            seleccion: "No anotan ambos",

            probabilidad: goles?.BTTS?.No,

            tipo: "goles",
          },
        ],

        "Mercado BTTS",
      ),
    );

    // ======================================================
    // CÓRNERS TOTALES
    // ======================================================

    candidatos.push(
      obtenerMayorProbabilidad(
        "Córners totales",

        [
          {
            seleccion: "Más de 9.5 córners",

            probabilidad: corners?.["Over 9.5"],

            tipo: "corners",
          },

          {
            seleccion: "Menos de 9.5 córners",

            probabilidad: corners?.["Under 9.5"],

            tipo: "corners",
          },
        ],

        "Total de córners del partido",
      ),
    );

    // ======================================================
    // CÓRNERS PRIMERA MITAD
    // ======================================================

    candidatos.push(
      obtenerMayorProbabilidad(
        "Córners 1T",

        [
          {
            seleccion: "Más de 4.5 córners 1T",

            probabilidad: corners?.["Over 4.5 1H"],

            tipo: "corners",
          },

          {
            seleccion: "Menos de 4.5 córners 1T",

            probabilidad: corners?.["Under 4.5 1H"],

            tipo: "corners",
          },
        ],

        "Primera mitad",
      ),
    );

    // ======================================================
    // CÓRNERS LOCAL 4.5
    // ======================================================

    candidatos.push(
      obtenerMayorProbabilidad(
        `${resultado.partido.local} - córners`,

        [
          {
            seleccion: `${resultado.partido.local} +4.5 córners`,

            probabilidad: corners?.["Home_Over_4.5"],

            tipo: "corners",
          },

          {
            seleccion: `${resultado.partido.local} -4.5 córners`,

            probabilidad: corners?.["Home_Under_4.5"],

            tipo: "corners",
          },
        ],

        "Mercado individual local",
      ),
    );

    // ======================================================
    // CÓRNERS LOCAL 5.5
    // ======================================================

    candidatos.push(
      obtenerMayorProbabilidad(
        `${resultado.partido.local} - línea 5.5`,

        [
          {
            seleccion: `${resultado.partido.local} +5.5 córners`,

            probabilidad: corners?.["Home_Over_5.5"],

            tipo: "corners",
          },

          {
            seleccion: `${resultado.partido.local} -5.5 córners`,

            probabilidad: corners?.["Home_Under_5.5"],

            tipo: "corners",
          },
        ],

        "Mercado individual local",
      ),
    );

    // ======================================================
    // CÓRNERS VISITANTE 3.5
    // ======================================================

    candidatos.push(
      obtenerMayorProbabilidad(
        `${resultado.partido.visitante} - córners`,

        [
          {
            seleccion: `${resultado.partido.visitante} +3.5 córners`,

            probabilidad: corners?.["Away_Over_3.5"],

            tipo: "corners",
          },

          {
            seleccion: `${resultado.partido.visitante} -3.5 córners`,

            probabilidad: corners?.["Away_Under_3.5"],

            tipo: "corners",
          },
        ],

        "Mercado individual visitante",
      ),
    );

    // ======================================================
    // CÓRNERS VISITANTE 4.5
    // ======================================================

    candidatos.push(
      obtenerMayorProbabilidad(
        `${resultado.partido.visitante} - línea 4.5`,

        [
          {
            seleccion: `${resultado.partido.visitante} +4.5 córners`,

            probabilidad: corners?.["Away_Over_4.5"],

            tipo: "corners",
          },

          {
            seleccion: `${resultado.partido.visitante} -4.5 córners`,

            probabilidad: corners?.["Away_Under_4.5"],

            tipo: "corners",
          },
        ],

        "Mercado individual visitante",
      ),
    );

    // ======================================================
    // TARJETAS
    // ======================================================

    candidatos.push(
      obtenerMayorProbabilidad(
        "Tarjetas",

        [
          {
            seleccion: "Más de 4.5 tarjetas",

            probabilidad: tarjetas?.["Over 4.5"],

            tipo: "tarjetas",
          },

          {
            seleccion: "Menos de 4.5 tarjetas",

            probabilidad: tarjetas?.["Under 4.5"],

            tipo: "tarjetas",
          },
        ],

        `Ajustado por ${resultado.partido.arbitro}`,
      ),
    );

    // ======================================================
    // LIMPIAR
    // ======================================================

    const ordenados = candidatos
      .filter(Boolean)
      .filter((item) => item.probabilidad >= 0 && item.probabilidad <= 1)
      .sort((a, b) => b.probabilidad - a.probabilidad);

    // ======================================================
    // TOP 5
    // ======================================================

    const top = ordenados.slice(0, 5);

    // ======================================================
    // SEÑAL PRINCIPAL
    // ======================================================

    const principal = top[0] || null;

    // ======================================================
    // MARCADOR EXACTO MÁS PROBABLE
    // ======================================================

    const marcador =
      Object.entries(goles?.Top_Scores || {})
        .map(([score, probability]) => ({
          marcador: score,

          probabilidad: Number(probability),
        }))
        .sort((a, b) => b.probabilidad - a.probabilidad)[0] || null;

    // ======================================================
    // TENDENCIA GENERAL
    // ======================================================

    const totalXg =
      Number(goles?.expected_goals_home || 0) +
      Number(goles?.expected_goals_away || 0);

    const tendencias = [];

    if (totalXg >= 2.8) {
      tendencias.push(
        "El modelo proyecta un partido con producción ofensiva elevada.",
      );
    }

    if (totalXg <= 2.1) {
      tendencias.push(
        "El modelo proyecta un partido de baja producción ofensiva.",
      );
    }

    if (Number(corners?.expected_total || 0) >= 9.5) {
      tendencias.push(
        "La expectativa de córners se encuentra por encima de la línea de 9.5.",
      );
    }

    if (Number(tarjetas?.expected_total || 0) >= 4.5) {
      tendencias.push("La proyección disciplinaria supera las 4.5 tarjetas.");
    }

    return {
      top,
      principal,
      marcador,
      tendencias,
    };
  }, [resultado, datosResultado]);

  // Logos de los equipos del resultado
  const logoLocal = useMemo(() => {
    const equipo = resultado?.partido?.local;

    if (!equipo) {
      return null;
    }

    return getTeamLogo(equipo);
  }, [resultado]);

  const logoVisitante = useMemo(() => {
    const equipo = resultado?.partido?.visitante;

    if (!equipo) {
      return null;
    }

    return getTeamLogo(equipo);
  }, [resultado]);

  // Exportar a PDF
  const exportarPdf = async () => {
    if (!resultado || !reportRef.current) {
      return;
    }

    setExportingPdf(true);

    try {
      await exportMatchReport({
        element: reportRef.current,
        local: resultado.partido.local,
        visitante: resultado.partido.visitante,
      });
    } catch (exportError) {
      console.error("Error generando PDF:", exportError);

      setError(
        exportError?.message || "No fue posible generar el reporte PDF.",
      );
    } finally {
      setExportingPdf(false);
    }
  };

  // Render
  return (
    <main className="match-page">
      {/* ================================================= */}
      {/* CONTENIDO PRINCIPAL */}
      {/* ================================================= */}

      <div className="match-main-area">
        <div className="match-shell">
          {/* ================================================= */}
          {/* FORMULARIO */}
          {/* ================================================= */}

          <section id="prediccion" className="match-prediction-block">
            <div className="match-prediction-block__heading">
              <div>
                <span className="match-block-kicker">Match Center</span>

                <h2>Configura el encuentro</h2>

                <p>
                  Selecciona los protagonistas del partido para ejecutar el
                  motor estadístico.
                </p>
              </div>

              <div className="match-step-badge">
                <span>PASO</span>

                <strong>01</strong>
              </div>
            </div>

            <form onSubmit={analizarPartido}>
              <div className="match-form-grid">
                {/* ======================================= */}
                {/* EQUIPO LOCAL */}
                {/* ======================================= */}

                <SportsSelect
                  label="Equipo local"
                  badge="HOME"
                  value={form.local}
                  options={catalogos.equipos}
                  placeholder="Seleccionar equipo local"
                  searchPlaceholder="Buscar equipo..."
                  loading={loadingCatalogos}
                  disabledValues={[form.visitante]}
                  variant="green"
                  showTeamLogo
                  onChange={(value) => actualizarCampo("local", value)}
                />

                {/* ======================================= */}
                {/* VS */}
                {/* ======================================= */}

                <div className="match-versus">
                  <span>VS</span>
                </div>

                {/* ======================================= */}
                {/* EQUIPO VISITANTE */}
                {/* ======================================= */}

                <SportsSelect
                  label="Equipo visitante"
                  badge="AWAY"
                  value={form.visitante}
                  options={catalogos.equipos}
                  placeholder="Seleccionar equipo visitante"
                  searchPlaceholder="Buscar equipo..."
                  loading={loadingCatalogos}
                  disabledValues={[form.local]}
                  variant="cyan"
                  showTeamLogo
                  onChange={(value) => actualizarCampo("visitante", value)}
                />

                {/* ======================================= */}
                {/* ÁRBITRO */}
                {/* ======================================= */}

                <SportsSelect
                  label="Árbitro"
                  badge="REF"
                  value={form.arbitro}
                  options={catalogos.arbitros}
                  placeholder="Seleccionar árbitro"
                  searchPlaceholder="Buscar árbitro..."
                  loading={loadingCatalogos}
                  variant="yellow"
                  onChange={(value) => actualizarCampo("arbitro", value)}
                />
              </div>

              {/* ========================================= */}
              {/* ERROR CATÁLOGOS */}
              {/* ========================================= */}

              {errorCatalogos && (
                <div className="match-error">
                  <div className="match-error__icon">!</div>

                  <div>
                    <strong>No fue posible conectar con Python</strong>

                    <span>{errorCatalogos}</span>
                  </div>
                </div>
              )}

              {/* ========================================= */}
              {/* ERROR GENERAL */}
              {/* ========================================= */}

              {error && (
                <div className="match-error">
                  <div className="match-error__icon">!</div>

                  <div>
                    <strong>No fue posible realizar el análisis</strong>

                    <span>{error}</span>
                  </div>
                </div>
              )}

              {/* ========================================= */}
              {/* ACCIONES */}
              {/* ========================================= */}

              <div className="match-search-actions">
                <div className="match-data-note">
                  {/* <span className="match-data-note__dot" />

                  <div>
                    <strong>Histórico local</strong>

                    <small>historial_ligamx_2023.csv</small>
                  </div> */}
                </div>

                <button
                  type="submit"
                  className="match-analyze-button"
                  disabled={
                    loading || loadingCatalogos || Boolean(errorCatalogos)
                  }
                >
                  {loading ? (
                    <>
                      <span className="match-spinner" />
                      Procesando modelo...
                    </>
                  ) : (
                    <>
                      Ejecutar análisis
                      <span className="match-analyze-button__arrow">→</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </section>

          {/* ================================================= */}
          {/* ANALÍTICA */}
          {/* ================================================= */}

          <section id="analitica" className="match-analysis-area">
            {/* =============================================== */}
            {/* EMPTY */}
            {/* =============================================== */}

            {!resultado && !loading && (
              <div className="match-empty-state">
                <div className="match-empty-state__visual">
                  <div className="match-empty-radar">
                    <span className="match-empty-radar__one" />

                    <span className="match-empty-radar__two" />

                    <span className="match-empty-radar__three" />

                    <strong>%</strong>
                  </div>
                </div>

                <span className="match-block-kicker">Analytics Center</span>

                <h2>Tu lectura del partido aparecerá aquí</h2>

                <p>
                  Selecciona un equipo local, visitante y árbitro para ejecutar
                  el análisis estadístico.
                </p>

                <div className="match-empty-state__markets">
                  <span>Resultado</span>

                  <span>Goles</span>

                  <span>Córners</span>

                  <span>Tarjetas</span>

                  <span>Marcadores</span>
                </div>
              </div>
            )}

            {/* =============================================== */}
            {/* LOADING */}
            {/* =============================================== */}

            {loading && (
              <div className="match-processing">
                <div className="match-processing__pitch">
                  <span />
                  <span />
                  <span />
                </div>

                <span className="match-block-kicker">Calculando</span>

                <h2>Procesando modelo estadístico</h2>

                <p>Generando probabilidades del encuentro.</p>
              </div>
            )}

            {/* =============================================== */}
            {/* RESULTADOS */}
            {/* =============================================== */}

            {resultado && datosResultado && !loading && (
              <>
                {/* ========================================= */}
                {/* TOOLBAR */}
                {/* FUERA DEL PDF */}
                {/* ========================================= */}

                <div className="match-results-toolbar">
                  <div className="match-results-toolbar__info">
                    <span className="match-results-toolbar__status">
                      <span />
                      Análisis completado
                    </span>

                    <div>
                      <strong>Reporte del encuentro</strong>

                      <small>
                        Exporta los resultados visibles en un documento PDF.
                      </small>
                    </div>
                  </div>

                  <ExportPdfButton
                    loading={exportingPdf}
                    onClick={exportarPdf}
                  />
                </div>

                {/* ========================================= */}
                {/* CONTENIDO DEL PDF */}
                {/* ========================================= */}

                <div ref={reportRef} className="match-results">
                  {/* ======================================= */}
                  {/* MATCH ANALYSIS */}
                  {/* ======================================= */}

                  <section className="match-fixture-card">
                    <div className="match-fixture-card__topline">
                      <span>MATCH ANALYSIS</span>

                      <div>
                        <span className="match-live-dot" />
                        Modelo procesado
                      </div>
                    </div>

                    <div className="match-fixture-card__main">
                      {/* ================================= */}
                      {/* LOCAL */}
                      {/* ================================= */}

                      <div className="match-team">
                        <span className="match-team-label">LOCAL</span>

                        <div className="match-team-emblem">
                          {logoLocal ? (
                            <img
                              src={logoLocal}
                              alt={resultado.partido.local}
                              className="match-team-emblem-image"
                            />
                          ) : (
                            <span className="match-team-emblem-fallback">
                              {obtenerInicialesEquipo(resultado.partido.local)}
                            </span>
                          )}
                        </div>

                        <h2>{resultado.partido.local}</h2>
                      </div>

                      {/* ================================= */}
                      {/* CENTRO */}
                      {/* ================================= */}

                      <div className="match-fixture-center">
                        <span>PREDICCIÓN</span>

                        <strong>VS</strong>

                        <div className="match-fixture-referee">
                          <span>Árbitro</span>

                          <b>{resultado.partido.arbitro}</b>
                        </div>
                      </div>

                      {/* ================================= */}
                      {/* VISITANTE */}
                      {/* ================================= */}

                      <div className="match-team">
                        <span className="match-team-label">VISITANTE</span>

                        <div className="match-team-emblem match-team-emblem--away">
                          {logoVisitante ? (
                            <img
                              src={logoVisitante}
                              alt={resultado.partido.visitante}
                              className="match-team-emblem-image"
                            />
                          ) : (
                            <span className="match-team-emblem-fallback">
                              {obtenerInicialesEquipo(
                                resultado.partido.visitante,
                              )}
                            </span>
                          )}
                        </div>

                        <h2>{resultado.partido.visitante}</h2>
                      </div>
                    </div>
                  </section>

                  {/* ======================================= */}
                  {/* H2H */}
                  {/* ======================================= */}

                  <section className="match-h2h-card">
                    <div className="match-h2h-icon">H2H</div>

                    <div className="match-h2h-card__content">
                      <span>Historial directo</span>

                      <p>{resultado.h2h?.resumen}</p>
                    </div>

                    <div className="match-h2h-card__badge">Histórico</div>
                  </section>

                  {/* ======================================= */}
                  {/* RESULTADO 1X2 */}
                  {/* ======================================= */}

                  <section className="match-dashboard-section">
                    <SectionHeader
                      code="1X2"
                      eyebrow="Resultado"
                      title="Probabilidad del partido"
                      description="Distribución probabilística entre victoria local, empate y victoria visitante."
                    />

                    <div className="match-result-layout">
                      <div className="match-chart-card">
                        <ResponsiveContainer width="100%" height={300}>
                          <BarChart
                            data={datosResultado.resultado1X2}
                            layout="vertical"
                            margin={{
                              top: 10,
                              right: 30,
                              bottom: 10,
                              left: 20,
                            }}
                          >
                            <CartesianGrid
                              strokeDasharray="4 4"
                              horizontal={false}
                              stroke="#e6ebf1"
                            />

                            <XAxis
                              type="number"
                              domain={[0, 100]}
                              tickFormatter={(value) => `${value}%`}
                              axisLine={false}
                              tickLine={false}
                            />

                            <YAxis
                              dataKey="name"
                              type="category"
                              width={120}
                              axisLine={false}
                              tickLine={false}
                            />

                            <Tooltip content={<CustomTooltip />} />

                            <Bar
                              dataKey="value"
                              name="Probabilidad"
                              radius={[0, 8, 8, 0]}
                              barSize={28}
                            >
                              {datosResultado.resultado1X2.map((entry) => (
                                <Cell key={entry.name} fill={entry.color} />
                              ))}
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                      </div>

                      <aside className="match-insight-card">
                        <div className="match-insight-card__label">
                          ESCENARIO DOMINANTE
                        </div>

                        <strong>
                          {datosResultado.ganador.value.toFixed(1)}%
                        </strong>

                        <h3>{datosResultado.ganador.name}</h3>

                        <div className="match-insight-divider" />

                        <p>Resultado individual con mayor probabilidad.</p>
                      </aside>
                    </div>
                  </section>

                  {/* ======================================= */}
                  {/* GOLES */}
                  {/* ======================================= */}

                  <section className="match-dashboard-section">
                    <SectionHeader
                      code="xG"
                      eyebrow="Mercado de goles"
                      title="Producción ofensiva esperada"
                      description="Expectativas y probabilidades derivadas del modelo de goles."
                    />

                    <div className="match-metrics-grid">
                      <MetricCard
                        label={`xG ${resultado.partido.local}`}
                        value={numero(datosResultado.goles.expected_goals_home)}
                        description="Goles esperados local"
                        variant="local"
                        tag="HOME"
                      />

                      <MetricCard
                        label={`xG ${resultado.partido.visitante}`}
                        value={numero(datosResultado.goles.expected_goals_away)}
                        description="Goles esperados visitante"
                        variant="away"
                        tag="AWAY"
                      />

                      <MetricCard
                        label="Total xG"
                        value={numero(
                          Number(datosResultado.goles.expected_goals_home) +
                            Number(datosResultado.goles.expected_goals_away),
                        )}
                        description="Expectativa conjunta"
                        tag="MATCH"
                      />
                    </div>

                    <div className="match-two-columns">
                      {/* ================================= */}
                      {/* OVER / UNDER */}
                      {/* ================================= */}

                      <div className="match-panel">
                        <div className="match-panel-title">
                          <div>
                            <span>OVER / UNDER</span>

                            <h3>Líneas de goles</h3>
                          </div>
                        </div>

                        <ProbabilityBar
                          label="Más de 1.5 goles"
                          value={datosResultado.goles?.Over_Under?.["Over 1.5"]}
                        />

                        <ProbabilityBar
                          label="Menos de 1.5 goles"
                          value={
                            datosResultado.goles?.Over_Under?.["Under 1.5"]
                          }
                          accent="slate"
                        />

                        <ProbabilityBar
                          label="Más de 2.5 goles"
                          value={datosResultado.goles?.Over_Under?.["Over 2.5"]}
                          accent="cyan"
                        />

                        <ProbabilityBar
                          label="Menos de 2.5 goles"
                          value={
                            datosResultado.goles?.Over_Under?.["Under 2.5"]
                          }
                          accent="purple"
                        />
                      </div>

                      {/* ================================= */}
                      {/* BTTS */}
                      {/* ================================= */}

                      <div className="match-panel">
                        <div className="match-panel-title">
                          <div>
                            <span>BTTS</span>

                            <h3>Ambos equipos anotan</h3>
                          </div>
                        </div>

                        <div className="match-pie-wrapper">
                          <ResponsiveContainer width="100%" height={240}>
                            <PieChart>
                              <Pie
                                data={datosResultado.ambosAnotan}
                                dataKey="value"
                                nameKey="name"
                                innerRadius={68}
                                outerRadius={96}
                                paddingAngle={4}
                              >
                                <Cell fill={COLORS.positive} />

                                <Cell fill={COLORS.negative} />
                              </Pie>

                              <Tooltip content={<CustomTooltip />} />

                              <Legend />
                            </PieChart>
                          </ResponsiveContainer>

                          <div className="match-pie-center">
                            <strong>
                              {porcentaje(
                                datosResultado.goles?.BTTS?.Yes,
                              ).toFixed(1)}
                              %
                            </strong>

                            <span>SÍ</span>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* ================================= */}
                    {/* MARCADOR EXACTO */}
                    {/* ================================= */}

                    <div className="match-panel match-panel--scores">
                      <div className="match-panel-title">
                        <div>
                          <span>MARCADOR EXACTO</span>

                          <h3>Top 5 resultados más probables</h3>
                        </div>
                      </div>

                      <ResponsiveContainer width="100%" height={300}>
                        <BarChart data={datosResultado.topMarcadores}>
                          <CartesianGrid
                            strokeDasharray="4 4"
                            vertical={false}
                            stroke="#e7ebf2"
                          />

                          <XAxis
                            dataKey="marcador"
                            axisLine={false}
                            tickLine={false}
                          />

                          <YAxis
                            axisLine={false}
                            tickLine={false}
                            tickFormatter={(value) => `${value}%`}
                          />

                          <Tooltip content={<CustomTooltip />} />

                          <Bar
                            dataKey="probabilidad"
                            name="Probabilidad"
                            fill={COLORS.local}
                            radius={[8, 8, 0, 0]}
                            barSize={48}
                          />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </section>

                  {/* ======================================= */}
                  {/* CÓRNERS */}
                  {/* ======================================= */}

                  <section className="match-dashboard-section">
                    <SectionHeader
                      code="CK"
                      eyebrow="Tiros de esquina"
                      title="Mercado de córners"
                      description="Expectativa general y distribución por equipo."
                    />

                    <div className="match-metrics-grid match-metrics-grid--four">
                      <MetricCard
                        label="Total esperado"
                        value={numero(datosResultado.corners.expected_total, 1)}
                        description="Partido completo"
                        variant="corner"
                        tag="TOTAL"
                      />

                      <MetricCard
                        label="Primera mitad"
                        value={numero(datosResultado.corners.expected_1H, 1)}
                        description="Córners esperados 1T"
                        tag="1H"
                      />

                      <MetricCard
                        label={resultado.partido.local}
                        value={numero(datosResultado.corners.expected_home, 1)}
                        description="Esperados local"
                        variant="local"
                        tag="HOME"
                      />

                      <MetricCard
                        label={resultado.partido.visitante}
                        value={numero(datosResultado.corners.expected_away, 1)}
                        description="Esperados visitante"
                        variant="away"
                        tag="AWAY"
                      />
                    </div>

                    <div className="match-two-columns">
                      {/* ================================= */}
                      {/* LÍNEAS CÓRNERS */}
                      {/* ================================= */}

                      <div className="match-panel">
                        <ProbabilityBar
                          label="Más de 9.5 córners"
                          value={datosResultado.corners?.["Over 9.5"]}
                          accent="orange"
                        />

                        <ProbabilityBar
                          label="Menos de 9.5 córners"
                          value={datosResultado.corners?.["Under 9.5"]}
                          accent="slate"
                        />

                        <ProbabilityBar
                          label="Más de 4.5 córners 1T"
                          value={datosResultado.corners?.["Over 4.5 1H"]}
                          accent="cyan"
                        />

                        <ProbabilityBar
                          label="Menos de 4.5 córners 1T"
                          value={datosResultado.corners?.["Under 4.5 1H"]}
                          accent="purple"
                        />
                      </div>

                      {/* ================================= */}
                      {/* GRÁFICA CÓRNERS */}
                      {/* ================================= */}

                      <div className="match-panel">
                        <ResponsiveContainer width="100%" height={260}>
                          <BarChart data={datosResultado.cornersEquipos}>
                            <CartesianGrid
                              strokeDasharray="4 4"
                              vertical={false}
                              stroke="#e7ebf2"
                            />

                            <XAxis
                              dataKey="name"
                              axisLine={false}
                              tickLine={false}
                            />

                            <YAxis axisLine={false} tickLine={false} />

                            <Tooltip />

                            <Bar
                              dataKey="esperado"
                              name="Córners esperados"
                              fill={COLORS.corner}
                              radius={[8, 8, 0, 0]}
                            />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                    {/* ================================= */}
                    {/* MERCADOS POR EQUIPO */}
                    {/* ================================= */}

                    <div className="match-team-markets">
                      {/* LOCAL */}

                      <div className="match-team-market-card">
                        <div className="match-team-market-card__heading">
                          <span>LOCAL</span>

                          <h3>{resultado.partido.local}</h3>
                        </div>

                        <ProbabilityBar
                          label="Más de 4.5 córners"
                          value={datosResultado.corners?.["Home_Over_4.5"]}
                        />

                        <ProbabilityBar
                          label="Menos de 4.5 córners"
                          value={datosResultado.corners?.["Home_Under_4.5"]}
                          accent="slate"
                        />

                        <ProbabilityBar
                          label="Más de 5.5 córners"
                          value={datosResultado.corners?.["Home_Over_5.5"]}
                          accent="cyan"
                        />

                        <ProbabilityBar
                          label="Menos de 5.5 córners"
                          value={datosResultado.corners?.["Home_Under_5.5"]}
                          accent="purple"
                        />
                      </div>

                      {/* VISITANTE */}

                      <div className="match-team-market-card">
                        <div className="match-team-market-card__heading">
                          <span>VISITANTE</span>

                          <h3>{resultado.partido.visitante}</h3>
                        </div>

                        <ProbabilityBar
                          label="Más de 3.5 córners"
                          value={datosResultado.corners?.["Away_Over_3.5"]}
                          accent="cyan"
                        />

                        <ProbabilityBar
                          label="Menos de 3.5 córners"
                          value={datosResultado.corners?.["Away_Under_3.5"]}
                          accent="slate"
                        />

                        <ProbabilityBar
                          label="Más de 4.5 córners"
                          value={datosResultado.corners?.["Away_Over_4.5"]}
                        />

                        <ProbabilityBar
                          label="Menos de 4.5 córners"
                          value={datosResultado.corners?.["Away_Under_4.5"]}
                          accent="purple"
                        />
                      </div>
                    </div>
                  </section>

                  {/* ======================================= */}
                  {/* TARJETAS */}
                  {/* ======================================= */}

                  <section className="match-dashboard-section">
                    <SectionHeader
                      code="YC"
                      eyebrow="Disciplina"
                      title="Mercado de tarjetas"
                      description={`Estimación ajustada según el árbitro ${resultado.partido.arbitro}.`}
                    />

                    <div className="match-card-market-layout">
                      <MetricCard
                        label="Tarjetas esperadas"
                        value={numero(
                          datosResultado.tarjetas.expected_total,
                          1,
                        )}
                        description={`Ajustadas por ${resultado.partido.arbitro}`}
                        variant="card"
                        tag="MATCH"
                      />

                      <div className="match-panel">
                        <ProbabilityBar
                          label="Más de 4.5 tarjetas"
                          value={datosResultado.tarjetas?.["Over 4.5"]}
                          accent="orange"
                        />

                        <ProbabilityBar
                          label="Menos de 4.5 tarjetas"
                          value={datosResultado.tarjetas?.["Under 4.5"]}
                          accent="slate"
                        />
                      </div>
                    </div>
                  </section>

                  {/* ======================================================= */}
                  {/* RESUMEN FINAL */}
                  {/* ======================================================= */}

                  {resumenProbabilidades && (
                    <section className="match-dashboard-section match-summary-section">
                      <SectionHeader
                        code="TOP"
                        eyebrow="Resumen final"
                        title="Señales de mayor probabilidad"
                        description="Lectura consolidada de los mercados con mayor probabilidad calculada por el modelo."
                      />

                      {/* =================================================== */}
                      {/* PRINCIPAL */}
                      {/* =================================================== */}

                      {resumenProbabilidades.principal && (
                        <div className="match-summary-highlight">
                          <div className="match-summary-highlight__content">
                            <span className="match-summary-highlight__eyebrow">
                              MAYOR PROBABILIDAD DEL MODELO
                            </span>

                            <h3>{resumenProbabilidades.principal.seleccion}</h3>

                            <p>{resumenProbabilidades.principal.categoria}</p>
                          </div>

                          <div className="match-summary-highlight__probability">
                            <strong>
                              {porcentaje(
                                resumenProbabilidades.principal.probabilidad,
                              ).toFixed(1)}
                              %
                            </strong>

                            <span>Probabilidad</span>
                          </div>
                        </div>
                      )}

                      {/* =================================================== */}
                      {/* TOP SEÑALES */}
                      {/* =================================================== */}

                      <div className="match-summary-ranking">
                        {resumenProbabilidades.top.map((item, index) => {
                          const probability = porcentaje(item.probabilidad);

                          let nivel = "Moderada";

                          if (probability >= 75) {
                            nivel = "Alta";
                          } else if (probability >= 65) {
                            nivel = "Fuerte";
                          }

                          return (
                            <article
                              key={`${item.categoria}-${item.seleccion}`}
                              className="match-summary-item"
                            >
                              <div className="match-summary-item__position">
                                {String(index + 1).padStart(2, "0")}
                              </div>

                              <div className="match-summary-item__body">
                                <span>{item.categoria}</span>

                                <strong>{item.seleccion}</strong>

                                <small>{item.descripcion}</small>
                              </div>

                              <div className="match-summary-item__score">
                                <strong>{probability.toFixed(1)}%</strong>

                                <span
                                  className={`match-summary-signal ${
                                    nivel === "Alta"
                                      ? "match-summary-signal--high"
                                      : nivel === "Fuerte"
                                        ? "match-summary-signal--strong"
                                        : ""
                                  }`}
                                >
                                  {nivel}
                                </span>
                              </div>
                            </article>
                          );
                        })}
                      </div>

                      {/* =================================================== */}
                      {/* LECTURA GENERAL */}
                      {/* =================================================== */}

                      <div className="match-summary-bottom">
                        <div className="match-summary-insights">
                          <span className="match-summary-title">
                            Lectura del encuentro
                          </span>

                          {resumenProbabilidades.tendencias.length > 0 ? (
                            resumenProbabilidades.tendencias.map(
                              (tendencia, index) => (
                                <div
                                  key={`${tendencia}-${index}`}
                                  className="match-summary-insight"
                                >
                                  <span />

                                  <p>{tendencia}</p>
                                </div>
                              ),
                            )
                          ) : (
                            <div className="match-summary-insight">
                              <span />

                              <p>
                                No se detecta una tendencia extrema adicional
                                entre los mercados analizados.
                              </p>
                            </div>
                          )}
                        </div>

                        {/* ================================================= */}
                        {/* MARCADOR */}
                        {/* ================================================= */}

                        {resumenProbabilidades.marcador && (
                          <div className="match-summary-score">
                            <span>MARCADOR MÁS PROBABLE</span>

                            <strong>
                              {resumenProbabilidades.marcador.marcador}
                            </strong>

                            <small>
                              {porcentaje(
                                resumenProbabilidades.marcador.probabilidad,
                              ).toFixed(1)}
                              % de probabilidad
                            </small>
                          </div>
                        )}
                      </div>

                      {/* =================================================== */}
                      {/* NOTA */}
                      {/* =================================================== */}

                      <div className="match-summary-disclaimer">
                        <span>i</span>

                        <p>
                          <strong>Interpretación estadística:</strong> una
                          probabilidad alta indica que el modelo considera ese
                          escenario más probable, pero no significa que sea una
                          apuesta rentable ni garantiza el resultado. Para
                          calcular valor esperado también se necesita conocer la
                          cuota ofrecida.
                        </p>
                      </div>
                    </section>
                  )}

                  {/* ======================================= */}
                  {/* FOOTER */}
                  {/* ======================================= */}

                  <footer className="match-results-footer">
                    <span className="match-live-dot" />
                    Resultados estadísticos basados en información histórica.
                    Las probabilidades no representan resultados garantizados.
                  </footer>
                </div>
              </>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}

export default MatchAnalytics;
