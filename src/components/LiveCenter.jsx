import axios from "axios";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { getTeamLogo } from "../utils/teamLogos";

import "./LiveCenter.css";

const API_URL = "";

// ============================================================
// POLLING UI
//
// React puede preguntar frecuentemente a NUESTRO backend.
//
// Eso NO significa que estemos consumiendo API-Football
// cada vez.
//
// FastAPI tiene cache independiente.
// ============================================================

const NORMAL_REFRESH_SECONDS = 60;

const LIVE_UI_REFRESH_SECONDS = 20;

const DETAIL_REFRESH_SECONDS = 90;

// ============================================================
// UTILIDADES
// ============================================================

const number = (value, fallback = 0) => {
  const n = Number(value);

  return Number.isFinite(n) ? n : fallback;
};

const percentage = (value) => {
  return `${(number(value) * 100).toFixed(1)}%`;
};

const formatStat = (value, suffix = "") => {
  if (value === null || value === undefined) {
    return "—";
  }

  return `${value}${suffix}`;
};

const isLiveStatus = (status) => {
  return ["1H", "HT", "2H", "ET", "BT", "P", "SUSP", "INT"].includes(status);
};

// ============================================================
// STATUS
// ============================================================

function LiveStatus({ match }) {
  const status = match?.status?.short;

  const minute = match?.status?.elapsed;

  const live =
    match?.live_verified ||
    ["1H", "HT", "2H", "ET", "BT", "P", "INT", "SUSP", "LIVE"].includes(status);

  if (live) {
    return (
      <span className="live-status live-status--active">
        <span />

        {status === "HT" ? "DESCANSO" : minute ? `${minute}'` : "EN VIVO"}
      </span>
    );
  }

  if (["FT", "AET", "PEN"].includes(status)) {
    return <span className="live-status live-status--finished">FINAL</span>;
  }

  if (match?.live_candidate) {
    return (
      <span className="live-status live-status--standby">
        <span />
        POR INICIAR
      </span>
    );
  }

  return (
    <span className="live-status live-status--scheduled">
      {match?.time_local || "NS"}
    </span>
  );
}

// ============================================================
// ESCUDO
// ============================================================

function TeamBadge({ team }) {
  const localLogo = getTeamLogo(team?.name);

  const logo = localLogo || team?.logo;

  return (
    <div className="live-team-badge">
      {logo ? (
        <img src={logo} alt={team?.name} />
      ) : (
        <span>
          {String(team?.name || "?")
            .trim()
            .slice(0, 2)
            .toUpperCase()}
        </span>
      )}
    </div>
  );
}

// ============================================================
// MATCH CARD
// ============================================================

function LiveMatchCard({ match, selected, onClick }) {
  const live = match?.live_verified;

  const finished = ["FT", "AET", "PEN"].includes(match?.status?.short);

  return (
    <button
      type="button"
      className={[
        "live-match-card",

        selected ? "live-match-card--selected" : "",

        live ? "live-match-card--live" : "",

        finished ? "live-match-card--finished" : "",
      ].join(" ")}
      onClick={onClick}
    >
      <div className="live-match-card__top">
        <LiveStatus match={match} />

        <span>{match.league?.round}</span>
      </div>

      <div className="live-match-card__team">
        <TeamBadge team={match.home} />

        <strong>{match.home?.name}</strong>

        <b className={live ? "live-score-number" : ""}>
          {match.home?.goals ?? "-"}
        </b>
      </div>

      <div className="live-match-card__team">
        <TeamBadge team={match.away} />

        <strong>{match.away?.name}</strong>

        <b className={live ? "live-score-number" : ""}>
          {match.away?.goals ?? "-"}
        </b>
      </div>

      {live && (
        <div className="live-match-card__live-strip">
          <span />

          <strong>LIVE DATA</strong>

          <small>API-Football</small>
        </div>
      )}

      <div className="live-match-card__footer">
        <span>{match.venue?.name || "Liga MX"}</span>

        <strong>Analizar →</strong>
      </div>
    </button>
  );
}

// ============================================================
// STAT
// ============================================================

function LiveStatRow({ label, home, away, suffix = "" }) {
  const homeValue = number(home);

  const awayValue = number(away);

  const total = homeValue + awayValue;

  const homeWidth = total > 0 ? (homeValue / total) * 100 : 50;

  return (
    <div className="live-stat-row">
      <div className="live-stat-row__values">
        <strong>{formatStat(home, suffix)}</strong>

        <span>{label}</span>

        <strong>{formatStat(away, suffix)}</strong>
      </div>

      <div className="live-stat-row__bar">
        <span
          style={{
            width: `${homeWidth}%`,
          }}
        />

        <span
          style={{
            width: `${100 - homeWidth}%`,
          }}
        />
      </div>
    </div>
  );
}

// ============================================================
// EVENTO
// ============================================================

const getEventIcon = (event) => {
  if (event.type === "Goal") {
    return "⚽";
  }

  if (event.type === "Card") {
    if (String(event.detail).toLowerCase().includes("red")) {
      return "🟥";
    }

    return "🟨";
  }

  if (event.type === "subst" || event.type === "Subst") {
    return "↔";
  }

  if (event.type === "Var") {
    return "VAR";
  }

  return "•";
};

// ============================================================
// PRINCIPAL
// ============================================================

function LiveCenter() {
  const [scope, setScope] = useState("live");

  const [matches, setMatches] = useState([]);

  const [selectedFixture, setSelectedFixture] = useState(null);

  // Partido seleccionado desde TheSportsDB
  const [selectedScheduleMatch, setSelectedScheduleMatch] = useState(null);

  // Resolviendo ID entre proveedores
  const [resolvingFixture, setResolvingFixture] = useState(false);

  const [liveMeta, setLiveMeta] = useState({
    overlayActive: false,
    overlayAvailable: false,
    stale: false,
    quota: null,
    providerRefreshSeconds: 300,
  });

  const [detail, setDetail] = useState(null);

  const [loadingMatches, setLoadingMatches] = useState(true);

  const [loadingDetail, setLoadingDetail] = useState(false);

  const [error, setError] = useState("");

  const [countdown, setCountdown] = useState(NORMAL_REFRESH_SECONDS);

  const [lastUpdated, setLastUpdated] = useState(null);

  // =========================================================
  // AI
  // =========================================================

  const [aiQuestion, setAiQuestion] = useState("");

  const [aiMessages, setAiMessages] = useState([]);

  const [aiLoading, setAiLoading] = useState(false);

  // =========================================================
  // PARTIDOS
  // =========================================================

  // ============================================================
  // CARGAR CARTELERA
  //
  // THE SPORTS DB
  // ============================================================

  const loadMatches = useCallback(
    async (silent = false) => {
      if (!silent) {
        setLoadingMatches(true);
      }

      try {
        const { data } = await axios.get(
          `${API_URL}/api/live`,

          {
            params: {
              scope,
            },
          },
        );

        if (!data?.success) {
          throw new Error("No fue posible cargar Live Center.");
        }

        const nextMatches = Array.isArray(data.matches) ? data.matches : [];

        setMatches(nextMatches);

        setLiveMeta({
          overlayActive: Boolean(data.overlay_active),

          overlayAvailable: Boolean(data.overlay_available),

          stale: Boolean(data.overlay_stale),

          quota: data.quota || null,

          providerRefreshSeconds: data.provider_refresh_seconds || 300,
        });

        setCountdown(data.ui_refresh_seconds || NORMAL_REFRESH_SECONDS);

        setLastUpdated(new Date());

        setError("");
      } catch (requestError) {
        console.error(requestError);

        setError(
          requestError?.response?.data?.detail ||
            requestError?.message ||
            "No fue posible actualizar Live Center.",
        );
      } finally {
        setLoadingMatches(false);
      }
    },

    [scope],
  );

  // ============================================================
  // SELECCIONAR PARTIDO
  //
  // TheSportsDB
  //      ↓
  // resolver
  //      ↓
  // API-Football fixture_id
  // ============================================================

  const seleccionarPartido = async (match) => {
    if (!match || resolvingFixture) {
      return;
    }

    setSelectedScheduleMatch(match);

    setAiMessages([]);

    setAiQuestion("");

    setError("");

    // =======================================================
    // YA TENEMOS FIXTURE ID
    //
    // gracias al Live Overlay.
    // =======================================================

    if (match.fixture_id) {
      setSelectedFixture(match.fixture_id);

      return;
    }

    // =======================================================
    // SI TODAVÍA NO TENEMOS FIXTURE ID
    //
    // resolver bajo demanda.
    // =======================================================

    setResolvingFixture(true);

    try {
      const { data } = await axios.post(
        `${API_URL}/api/live/resolve`,

        {
          event_id: match.sportsdb_event_id,

          date: match.date_local,

          home: match.home?.name,

          away: match.away?.name,
        },
      );

      if (!data?.success || !data?.fixture_id) {
        throw new Error("No fue posible identificar el fixture.");
      }

      setSelectedFixture(data.fixture_id);
    } catch (requestError) {
      console.error(requestError);

      setError(
        requestError?.response?.data?.detail ||
          "Live Intelligence todavía no está disponible para este partido.",
      );
    } finally {
      setResolvingFixture(false);
    }
  };

  // =========================================================
  // DETALLE
  // =========================================================

  const loadDetail = useCallback(async (fixtureId, silent = false) => {
    if (!fixtureId) {
      return;
    }

    if (!silent) {
      setLoadingDetail(true);
    }

    try {
      const { data } = await axios.get(`${API_URL}/api/live/${fixtureId}`);

      if (!data?.success) {
        throw new Error("No fue posible obtener el partido.");
      }

      setDetail(data.data);

      const liveDetail = data.data;

      setMatches((current) =>
        current.map((match) => {
          if (
            match.fixture_id !== liveDetail.fixture_id &&
            match.fixture_id !== liveDetail.id
          ) {
            return match;
          }

          return {
            ...match,

            live_verified: ["1H", "HT", "2H", "ET", "BT", "P"].includes(
              liveDetail?.status?.short,
            ),

            status: liveDetail.status,

            home: {
              ...match.home,

              goals: liveDetail?.home?.goals,
            },

            away: {
              ...match.away,

              goals: liveDetail?.away?.goals,
            },
          };
        }),
      );

      setLastUpdated(new Date());
    } catch (requestError) {
      console.error(requestError);

      setError(
        requestError?.response?.data?.detail ||
          requestError?.message ||
          "No fue posible actualizar el partido.",
      );
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  // ============================================================
  // POLLING CARTELERA
  //
  // TheSportsDB
  //
  // 1 request cada 5 minutos
  //
  // Y SE DETIENE cuando estamos viendo un partido.
  // ============================================================

  useEffect(() => {
    loadMatches();

    if (selectedFixture) {
      return undefined;
    }

    const intervalSeconds = liveMeta.overlayActive
      ? LIVE_UI_REFRESH_SECONDS
      : NORMAL_REFRESH_SECONDS;

    const interval = window.setInterval(
      () => {
        loadMatches(true);
      },

      intervalSeconds * 1000,
    );

    return () => window.clearInterval(interval);
  }, [loadMatches, selectedFixture, liveMeta.overlayActive]);

  // ============================================================
  // POLLING PARTIDO SELECCIONADO
  //
  // API-Football
  //
  // 1 request / minuto
  // ============================================================

  useEffect(() => {
    if (!selectedFixture) {
      return undefined;
    }

    loadDetail(selectedFixture);

    const interval = window.setInterval(
      () => {
        loadDetail(selectedFixture, true);
      },

      DETAIL_REFRESH_SECONDS * 1000,
    );

    return () => window.clearInterval(interval);
  }, [selectedFixture, loadDetail]);

  // ============================================================
  // COUNTDOWN
  // ============================================================

  useEffect(() => {
    const timer = window.setInterval(
      () => {
        setCountdown((current) => {
          if (current <= 1) {
            return selectedFixture
              ? LIVE_UI_REFRESH_SECONDS
              : NORMAL_REFRESH_SECONDS;
          }

          return current - 1;
        });
      },

      1000,
    );

    return () => window.clearInterval(timer);
  }, [selectedFixture]);

  // =========================================================
  // CAMBIAR SCOPE
  // =========================================================

  const changeScope = (nextScope) => {
    setScope(nextScope);

    setSelectedFixture(null);

    setDetail(null);

    setAiMessages([]);

    setAiQuestion("");
  };

  // =========================================================
  // STATS
  // =========================================================

  const getStat = (side, name) => {
    return detail?.statistics?.[side]?.values?.[name] ?? null;
  };

  // =========================================================
  // INTELLIGENCE
  // =========================================================

  const intelligence = detail?.intelligence || {};

  const momentum = intelligence?.momentum || {
    home: 50,
    away: 50,
    trend: [],
  };

  const shift = intelligence?.probability_shift;

  const signals = intelligence?.signals || [];

  // =========================================================
  // AI
  // =========================================================

  const askAI = async (forcedQuestion = "") => {
    const question = String(forcedQuestion || aiQuestion).trim();

    if (!question || !selectedFixture || aiLoading) {
      return;
    }

    setAiMessages((current) => [
      ...current,
      {
        role: "user",

        content: question,
      },
    ]);

    setAiQuestion("");

    setAiLoading(true);

    try {
      const { data } = await axios.post(
        `${API_URL}/api/live/${selectedFixture}/ai`,
        {
          question,
        },
      );

      if (!data?.success) {
        throw new Error("No fue posible consultar MatchLab AI.");
      }

      setAiMessages((current) => [
        ...current,
        {
          role: "assistant",

          content: data.answer,

          provider: data.provider,
        },
      ]);
    } catch (requestError) {
      setAiMessages((current) => [
        ...current,
        {
          role: "assistant",

          content:
            requestError?.response?.data?.detail ||
            "MatchLab AI no está disponible en este momento.",

          error: true,
        },
      ]);
    } finally {
      setAiLoading(false);
    }
  };

  // =========================================================
  // LOGOS
  // =========================================================

  const homeLogo = useMemo(
    () => (detail ? getTeamLogo(detail.home?.name) || detail.home?.logo : null),
    [detail],
  );

  const awayLogo = useMemo(
    () => (detail ? getTeamLogo(detail.away?.name) || detail.away?.logo : null),
    [detail],
  );

  // =========================================================
  // RENDER
  // =========================================================

  return (
    <section id="en-vivo" className="live-center">
      {/* ================================================= */}
      {/* HERO */}
      {/* ================================================= */}

      {/* <div className="live-center__hero">
        <div className="live-center__hero-glow" />

        <div className="live-center__shell">
          <div className="live-center__hero-content">
            <div>
              <span className="live-center__kicker">
                <span />
                StatMX En Vivo
              </span>

              <h2>
                Sigue a tu equipo favorito.
                <strong> En tiempo real.</strong>
              </h2>

              <p>
                Sigue los encuentros de la Liga MX, analiza estadísticas, detecta
                cambios de momentum y consulta a Stat AI durante los 90
                minutos.
              </p>
            </div>

            <div className="live-engine-status">
              <div className="live-engine-status__radar">
                <span />
                <span />
                <strong>EN VIVO</strong>
              </div>

              <div>
                <span>MOTOR</span>

                <strong>Inteligencia en tiempo real</strong>

                <small>Recarga cada {REFRESH_SECONDS}s</small>
              </div>
            </div>
          </div>
        </div>
      </div> */}

      {/* ================================================= */}
      {/* BODY */}
      {/* ================================================= */}

      <div className="live-center__body">
        <div className="live-center__shell">
          {/* ============================================= */}
          {/* TOOLBAR */}
          {/* ============================================= */}

          <div className="live-toolbar">
            <div className="live-toolbar__tabs">
              <button
                type="button"
                className={scope === "live" ? "active" : ""}
                onClick={() => changeScope("live")}
              >
                <span className="live-toolbar__live-dot" />
                Ventana live
              </button>

              <button
                type="button"
                className={scope === "today" ? "active" : ""}
                onClick={() => changeScope("today")}
              >
                Partidos de hoy
              </button>
            </div>

            <div className="live-engine-status">
              <div className="live-engine-status__radar">
                <span />
                <span />

                <strong>{liveMeta.overlayActive ? "LIVE" : "READY"}</strong>
              </div>

              <div>
                <span>MOTOR</span>

                <strong>
                  {liveMeta.overlayActive
                    ? "Live Overlay activo"
                    : "Inteligencia en espera"}
                </strong>

                <small>
                  {liveMeta.overlayActive
                    ? `Datos live cada ${liveMeta.providerRefreshSeconds}s`
                    : "Se activará cerca del kickoff"}
                </small>
              </div>
            </div>

            <div className="live-toolbar__refresh">
              <span>Próxima actualización</span>

              <strong>{countdown}s</strong>

              <button
                type="button"
                onClick={() => {
                  loadMatches();
                  if (selectedFixture) {
                    loadDetail(selectedFixture);
                  }
                }}
              >
                ↻
              </button>
            </div>
          </div>

          <div className="live-provider-strip">
            <div>
              <span className="live-provider-strip__dot live-provider-strip__dot--schedule" />

              <div>
                <strong>TheSportsDB</strong>

                <small>Calendario de Liga MX</small>
              </div>
            </div>

            <span className="live-provider-strip__connector">→</span>

            <div>
              <span className="live-provider-strip__dot live-provider-strip__dot--live" />

              <div>
                <strong>API-Football</strong>

                <small>Live data bajo demanda</small>
              </div>
            </div>

            <span className="live-provider-strip__connector">→</span>

            <div>
              <span className="live-provider-strip__dot live-provider-strip__dot--ai" />

              <div>
                <strong>MatchLab Intelligence</strong>

                <small>Modelo + AI</small>
              </div>
            </div>
          </div>

          {liveMeta.quota && (
            <div
              className={`live-quota ${
                liveMeta.quota.remaining === 0 ? "live-quota--empty" : ""
              }`}
            >
              <div className="live-quota__status">
                <span />

                <div>
                  <strong>API-Football</strong>

                  <small>Live Overlay</small>
                </div>
              </div>

              <div className="live-quota__right">
                {liveMeta.quota.limit !== null && (
                  <>
                    <strong>
                      {liveMeta.quota.remaining ?? "—"}
                      {" / "}
                      {liveMeta.quota.limit}
                    </strong>

                    <small>requests disponibles</small>
                  </>
                )}
              </div>
            </div>
          )}

          {/* ============================================= */}
          {/* ERROR */}
          {/* ============================================= */}

          {error && (
            <div className="live-error">
              <strong>Live Center</strong>

              <span>{error}</span>
            </div>
          )}

          {/* ============================================= */}
          {/* MATCHES */}
          {/* ============================================= */}

          <div className="live-match-section">
            <div className="live-section-title">
              <div>
                <span>LIGA MX</span>

                <h3>
                  {scope === "live" ? "Partidos en vivo" : "Partidos de hoy"}
                </h3>
              </div>

              <small>{matches.length} encuentros</small>
            </div>

            {loadingMatches ? (
              <div className="live-match-loading">
                <span />
                <span />
                <span />

                <p>Buscando partidos de la Liga MX...</p>
              </div>
            ) : matches.length > 0 ? (
              <div className="live-match-grid">
                {matches.map((match) => (
                  <LiveMatchCard
                    key={match.id}
                    match={match}
                    selected={selectedScheduleMatch?.id === match.id}
                    onClick={() => seleccionarPartido(match)}
                  />
                ))}
              </div>
            ) : (
              <div className="live-empty">
                <div className="live-empty__radar">
                  <span />
                  <span />
                  <span />

                  <strong>EN VIVO</strong>
                </div>

                <h3>No hay partidos de Liga MX en vivo</h3>

                <p>
                  StatMX seguirá consultando automáticamente. También puedes
                  revisar los partidos programados para hoy.
                </p>

                {scope === "live" && (
                  <button type="button" onClick={() => changeScope("today")}>
                    Ver partidos de hoy
                  </button>
                )}
              </div>
            )}
          </div>

          {resolvingFixture && (
            <div className="live-resolving">
              <div className="live-resolving__radar">
                <span />

                <span />

                <strong>LIVE</strong>
              </div>

              <div>
                <span>MATCHLAB LIVE</span>

                <h3>Activando Live Intelligence</h3>

                <p>
                  Relacionando el encuentro con el proveedor de datos en vivo...
                </p>
              </div>
            </div>
          )}

          {/* ============================================= */}
          {/* DETALLE */}
          {/* ============================================= */}

          {selectedFixture && (
            <div className="live-analysis">
              {loadingDetail && !detail ? (
                <div className="live-detail-loading">
                  <span />
                  Procesando Live Intelligence...
                </div>
              ) : (
                detail && (
                  <>
                    {/* ===================================== */}
                    {/* SCOREBOARD */}
                    {/* ===================================== */}

                    <section className="live-scoreboard">
                      <div className="live-scoreboard__top">
                        <span>StatMX en vivo</span>

                        <div>
                          <span className="live-toolbar__live-dot" />

                          {detail.status?.short === "HT"
                            ? "DESCANSO"
                            : `${detail.status?.elapsed || 0}'`}
                        </div>
                      </div>

                      <div className="live-scoreboard__main">
                        <div className="live-score-team">
                          <span>LOCAL</span>

                          <div className="live-score-team__logo">
                            {homeLogo && (
                              <img src={homeLogo} alt={detail.home?.name} />
                            )}
                          </div>

                          <h3>{detail.home?.name}</h3>
                        </div>

                        <div className="live-score">
                          <span>{detail.status?.elapsed || 0}'</span>

                          <div>
                            <strong>{detail.home?.goals ?? 0}</strong>

                            <b>-</b>

                            <strong>{detail.away?.goals ?? 0}</strong>
                          </div>

                          <small>{detail.venue?.name || "Liga MX"}</small>
                        </div>

                        <div className="live-score-team">
                          <span>VISITANTE</span>

                          <div className="live-score-team__logo live-score-team__logo--away">
                            {awayLogo && (
                              <img src={awayLogo} alt={detail.away?.name} />
                            )}
                          </div>

                          <h3>{detail.away?.name}</h3>
                        </div>
                      </div>

                      <div className="live-scoreboard__meta">
                        <span>
                          Árbitro:
                          <strong> {detail.referee || "No disponible"}</strong>
                        </span>

                        <span>
                          Actualizado:
                          <strong>
                            {" "}
                            {lastUpdated
                              ? lastUpdated.toLocaleTimeString("es-MX")
                              : "—"}
                          </strong>
                        </span>
                      </div>
                    </section>

                    {/* ===================================== */}
                    {/* MOMENTUM */}
                    {/* ===================================== */}

                    <section className="live-panel live-momentum">
                      <div className="live-panel__heading">
                        <div>
                          <span>Inteligencia en tiempo real</span>

                          <h3>Impulso del partido</h3>

                          <p>{momentum.window}</p>
                        </div>

                        <div className="live-ai-badge">
                          ML
                          <span>Intelligence</span>
                        </div>
                      </div>

                      <div className="live-momentum__teams">
                        <div>
                          <strong>{detail.home?.name}</strong>

                          <b>{number(momentum.home).toFixed(1)}%</b>
                        </div>

                        <div>
                          <strong>{detail.away?.name}</strong>

                          <b>{number(momentum.away).toFixed(1)}%</b>
                        </div>
                      </div>

                      <div className="live-momentum__bar">
                        <span
                          style={{
                            width: `${momentum.home}%`,
                          }}
                        />

                        <span
                          style={{
                            width: `${momentum.away}%`,
                          }}
                        />

                        <i />
                      </div>

                      {momentum.trend?.length >= 2 && (
                        <div className="live-momentum-chart">
                          <ResponsiveContainer width="100%" height={240}>
                            <LineChart data={momentum.trend}>
                              <CartesianGrid
                                strokeDasharray="4 4"
                                vertical={false}
                                stroke="#e8edf2"
                              />

                              <XAxis
                                dataKey="minute"
                                tickFormatter={(value) => `${value}'`}
                                axisLine={false}
                                tickLine={false}
                              />

                              <YAxis
                                domain={[0, 100]}
                                tickFormatter={(value) => `${value}%`}
                                axisLine={false}
                                tickLine={false}
                              />

                              <Tooltip
                                formatter={(value) =>
                                  `${Number(value).toFixed(1)}%`
                                }
                                labelFormatter={(value) => `Minuto ${value}`}
                              />

                              <Line
                                type="monotone"
                                dataKey="home"
                                name={detail.home?.name}
                                stroke="#20c997"
                                strokeWidth={3}
                                dot={false}
                              />

                              <Line
                                type="monotone"
                                dataKey="away"
                                name={detail.away?.name}
                                stroke="#38bdf8"
                                strokeWidth={3}
                                dot={false}
                              />
                            </LineChart>
                          </ResponsiveContainer>
                        </div>
                      )}
                    </section>

                    {/* ===================================== */}
                    {/* STATS + SIGNALS */}
                    {/* ===================================== */}

                    <div className="live-two-column">
                      <section className="live-panel">
                        <div className="live-panel__heading">
                          <div>
                            <span>DATOS DEL PARTIDO</span>

                            <h3>Estadísticas en vivo</h3>
                          </div>
                        </div>

                        <LiveStatRow
                          label="Posesión"
                          home={getStat("home", "Ball Possession")}
                          away={getStat("away", "Ball Possession")}
                          suffix="%"
                        />

                        <LiveStatRow
                          label="Tiros"
                          home={getStat("home", "Total Shots")}
                          away={getStat("away", "Total Shots")}
                        />

                        <LiveStatRow
                          label="A portería"
                          home={getStat("home", "Shots on Goal")}
                          away={getStat("away", "Shots on Goal")}
                        />

                        <LiveStatRow
                          label="Córners"
                          home={getStat("home", "Corner Kicks")}
                          away={getStat("away", "Corner Kicks")}
                        />

                        <LiveStatRow
                          label="Faltas"
                          home={getStat("home", "Fouls")}
                          away={getStat("away", "Fouls")}
                        />

                        <LiveStatRow
                          label="Amarillas"
                          home={getStat("home", "Yellow Cards")}
                          away={getStat("away", "Yellow Cards")}
                        />
                      </section>

                      <section className="live-panel">
                        <div className="live-panel__heading">
                          <div>
                            <span>DETECTOR DE SEÑALES</span>

                            <h3>Señales del partido</h3>
                          </div>
                        </div>

                        <div className="live-signals">
                          {signals.length > 0 ? (
                            signals.map((signal, index) => (
                              <article
                                key={`${signal.type}-${index}`}
                                className={`live-signal live-signal--${signal.level}`}
                              >
                                <span>
                                  {String(index + 1).padStart(2, "0")}
                                </span>

                                <div>
                                  <strong>{signal.title}</strong>

                                  <p>{signal.description}</p>
                                </div>
                              </article>
                            ))
                          ) : (
                            <div className="live-signal-empty">
                              El motor todavía no detecta una señal dominante.
                            </div>
                          )}
                        </div>
                      </section>
                    </div>

                    {/* ===================================== */}
                    {/* PREMATCH VS LIVE */}
                    {/* ===================================== */}

                    {shift && (
                      <section className="live-panel">
                        <div className="live-panel__heading">
                          <div>
                            <span>CAMBIO DE MODELO</span>

                            <h3>Pre-match vs Live</h3>

                            <p>
                              Cómo cambió la lectura del modelo desde el inicio.
                            </p>
                          </div>
                        </div>

                        <div className="live-shift-grid">
                          {[
                            {
                              key: "home",
                              label: detail.home?.name,
                            },

                            {
                              key: "draw",
                              label: "Empate",
                            },

                            {
                              key: "away",
                              label: detail.away?.name,
                            },
                          ].map((option) => {
                            const item = shift[option.key];

                            return (
                              <article
                                key={option.key}
                                className="live-shift-card"
                              >
                                <span>{option.label}</span>

                                <div className="live-shift-card__probabilities">
                                  <div>
                                    <small>PRE</small>

                                    <strong>{percentage(item.prematch)}</strong>
                                  </div>

                                  <b>→</b>

                                  <div>
                                    <small>LIVE</small>

                                    <strong>{percentage(item.live)}</strong>
                                  </div>
                                </div>

                                <div
                                  className={`live-shift-change ${
                                    item.change >= 0
                                      ? "live-shift-change--up"
                                      : "live-shift-change--down"
                                  }`}
                                >
                                  {item.change >= 0 ? "▲" : "▼"}{" "}
                                  {Math.abs(item.change * 100).toFixed(1)}
                                  {" pp"}
                                </div>
                              </article>
                            );
                          })}
                        </div>

                        <div className="live-model-note">
                          La proyección live utiliza marcador actual, minuto y
                          expectativa de goles del modelo Dixon-Coles.
                        </div>
                      </section>
                    )}

                    {/* ===================================== */}
                    {/* TIMELINE */}
                    {/* ===================================== */}

                    <section className="live-panel">
                      <div className="live-panel__heading">
                        <div>
                          <span>CRONOLOGIA DEL PARTIDO</span>

                          <h3>Historia del encuentro</h3>
                        </div>

                        <small>{detail.events?.length || 0} eventos</small>
                      </div>

                      <div className="live-timeline">
                        {detail.events?.length > 0 ? (
                          [...detail.events].reverse().map((event, index) => (
                            <article
                              key={`${event.elapsed}-${index}`}
                              className="live-timeline-event"
                            >
                              <div className="live-timeline-event__minute">
                                {event.elapsed || 0}'
                                {event.extra ? `+${event.extra}` : ""}
                              </div>

                              <div className="live-timeline-event__line">
                                <span />
                              </div>

                              <div className="live-timeline-event__icon">
                                {getEventIcon(event)}
                              </div>

                              <div className="live-timeline-event__content">
                                <strong>
                                  {event.player || event.team || event.type}
                                </strong>

                                <span>{event.detail}</span>

                                {event.assist && (
                                  <small>Asistencia: {event.assist}</small>
                                )}
                              </div>
                            </article>
                          ))
                        ) : (
                          <div className="live-timeline-empty">
                            Todavía no existen eventos registrados para este
                            partido.
                          </div>
                        )}
                      </div>
                    </section>

                    {/* ===================================== */}
                    {/* AI */}
                    {/* ===================================== */}

                    <section className="live-ai">
                      <div className="live-ai__header">
                        <div className="live-ai__identity">
                          <div className="live-ai__logo">✦</div>

                          <div>
                            <span>StatMX AI</span>

                            <h3>Analista de partidos en directo</h3>

                            <p>
                              Pregunta sobre lo que está ocurriendo en el
                              partido.
                            </p>
                          </div>
                        </div>

                        <div className="live-ai__status">
                          <span />
                          BASADO EN DATOS
                        </div>
                      </div>

                      <div className="live-ai__suggestions">
                        {[
                          "¿Quién está dominando realmente?",
                          "¿Qué cambió respecto al pre-match?",
                          "¿Qué señales importantes detectas?",
                          "Resume los últimos minutos",
                        ].map((question) => (
                          <button
                            key={question}
                            type="button"
                            disabled={aiLoading}
                            onClick={() => askAI(question)}
                          >
                            {question}
                          </button>
                        ))}
                      </div>

                      <div className="live-ai__conversation">
                        {aiMessages.length === 0 ? (
                          <div className="live-ai__welcome">
                            <span>✦</span>

                            <div>
                              <strong>Estoy leyendo el partido.</strong>

                              <p>
                                Puedo interpretar el impulso, estadísticas,
                                eventos y cambios de probabilidad utilizando
                                únicamente los datos disponibles.
                              </p>
                            </div>
                          </div>
                        ) : (
                          aiMessages.map((message, index) => (
                            <div
                              key={`${message.role}-${index}`}
                              className={`live-ai-message live-ai-message--${message.role}`}
                            >
                              <span>
                                {message.role === "assistant" ? "✦" : "TÚ"}
                              </span>

                              <div>
                                {message.content}

                                {message.provider && (
                                  <small>
                                    {message.provider === "openai"
                                      ? "MatchLab AI"
                                      : "MatchLab Local Analyst"}
                                  </small>
                                )}
                              </div>
                            </div>
                          ))
                        )}

                        {aiLoading && (
                          <div className="live-ai-thinking">
                            <span />
                            <span />
                            <span />
                            Analizando partido...
                          </div>
                        )}
                      </div>

                      <div className="live-ai__input">
                        <input
                          value={aiQuestion}
                          onChange={(event) =>
                            setAiQuestion(event.target.value)
                          }
                          onKeyDown={(event) => {
                            if (event.key === "Enter") {
                              askAI();
                            }
                          }}
                          placeholder="Pregunta a MatchLab AI..."
                        />

                        <button
                          type="button"
                          disabled={!aiQuestion.trim() || aiLoading}
                          onClick={() => askAI()}
                        >
                          →
                        </button>
                      </div>

                      <div className="live-ai__disclaimer">
                        StatMX AI interpreta datos estadísticos disponibles y no
                        inventa eventos ni garantiza resultados.
                      </div>
                    </section>
                  </>
                )
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

export default LiveCenter;
