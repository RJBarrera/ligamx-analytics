import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faChartColumn,
  faEnvelope,
  faFileLines,
  faShieldHalved,
  faChartLine,
  faBrain,
  faTowerBroadcast,
  faChevronRight,
  faFutbol
} from "@fortawesome/free-solid-svg-icons";

import { getTeamLogo } from "../utils/teamLogos";
import "./Footer.css";

const CONTACT_EMAIL = "contacto@goalx.com";

function Footer() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="goalx-footer">
      <div className="goalx-footer__container">
        <div className="goalx-footer__content">
          <section className="goalx-footer__brand">
            <div className="goalx-footer__brand-header">
              <div className="goalx-footer__logo-wrapper">
                <img
                  src={getTeamLogo("logo")}
                  alt="GoalX"
                  className="goalx-footer__logo"
                />
              </div>

              <div className="goalx-footer__brand-text">
                <div className="goalx-footer__name">
                  Goal<span>X</span>
                </div>

                <div className="goalx-footer__tagline">
                  <span className="goalx-footer__status-dot" /> ANÁLISIS DE TU
                  LIGA FAVORITA
                </div>
              </div>
            </div>

            <p className="goalx-footer__description">
              Datos historicos. Análisis. Mejores decisiones.
              <br />
              Estadísticas y predicciones
              <br className="goalx-footer__desktop-break" /> para entender mejor
              cada partido.
            </p>
          </section>

          <section className="goalx-footer__column goalx-footer__navigation">
            <div className="goalx-footer__column-title">
              <span className="goalx-footer__title-icon">
                <FontAwesomeIcon icon={faChartLine} />
              </span>

              <span>Navegación</span>
            </div>

            <nav className="goalx-footer__nav">
              <a href="#prediccion">
                <FontAwesomeIcon icon={faChartColumn} />
                <span>Predicción</span>
              </a>

              <a href="#analitica">
                <FontAwesomeIcon icon={faChartLine} />
                <span>Analítica</span>
              </a>

              <a href="#modelo">
                <FontAwesomeIcon icon={faBrain} />
                <span>Modelo</span>
              </a>

              <a href="#en-vivo">
                <FontAwesomeIcon icon={faTowerBroadcast} />

                <span>En Vivo</span>

                <span className="goalx-footer__live-badge">LIVE</span>
              </a>
            </nav>
          </section>

          <section className="goalx-footer__column">
            <div className="goalx-footer__column-title">
              <span className="goalx-footer__title-icon">
                <FontAwesomeIcon icon={faShieldHalved} />
              </span>

              <span>Legal</span>
            </div>

            <div className="goalx-footer__links">
              <a
                href="/terminos-de-servicio"
                className="goalx-footer__link-row"
              >
                <span className="goalx-footer__link-icon">
                  <FontAwesomeIcon icon={faFileLines} />
                </span>

                <span className="goalx-footer__link-text">
                  Términos de servicio
                </span>

                <span className="goalx-footer__arrow">
                  <FontAwesomeIcon icon={faChevronRight} />
                </span>
              </a>

              <a
                href="/politica-de-privacidad"
                className="goalx-footer__link-row"
              >
                <span className="goalx-footer__link-icon">
                  <FontAwesomeIcon icon={faShieldHalved} />
                </span>

                <span className="goalx-footer__link-text">
                  Política de privacidad
                </span>

                <span className="goalx-footer__arrow">
                  <FontAwesomeIcon icon={faChevronRight} />
                </span>
              </a>
            </div>
          </section>

          <section className="goalx-footer__column">
            <div className="goalx-footer__column-title">
              <span className="goalx-footer__title-icon">
                <FontAwesomeIcon icon={faEnvelope} />
              </span>

              <span>Contacto</span>
            </div>

            <div className="goalx-footer__links">
              <a
                href={`mailto:${CONTACT_EMAIL}`}
                className="goalx-footer__link-row goalx-footer__contact-row"
              >
                <span className="goalx-footer__link-icon">
                  <FontAwesomeIcon icon={faEnvelope} />
                </span>

                <span className="goalx-footer__link-text">{CONTACT_EMAIL}</span>

                <span className="goalx-footer__arrow">
                  <FontAwesomeIcon icon={faChevronRight} />
                </span>
              </a>
            </div>
          </section>
        </div>
      </div>

      <div className="goalx-footer__bottom">
        <div className="goalx-footer__bottom-container">
          <p>© {currentYear} GoalX. Todos los derechos reservados.</p>

          <p className="goalx-footer__bottom-message">
            Datos · Análisis · Fútbol <FontAwesomeIcon icon={faFutbol} />
          </p>
        </div>
      </div>
    </footer>
  );
}

export default Footer;
