
import "./ExportPdfButton.css";

function ExportPdfButton({ loading = false, onClick }) {
  return (
    <button
      type="button"
      className="match-export-button"
      disabled={loading}
      onClick={onClick}
    >
      <span className="match-export-button__icon">
        {loading ? (
          <span className="match-export-button__spinner" />
        ) : (
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path
              d="M12 3v11m0 0 4-4m-4 4-4-4M5 17v3h14v-3"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.9"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        )}
      </span>

      <span className="match-export-button__content">
        <strong>{loading ? "Generando PDF..." : "Exportar reporte"}</strong>

        <small>{loading ? "Preparando análisis" : "Documento PDF"}</small>
      </span>

      {!loading && <span className="match-export-button__type">PDF</span>}
    </button>
  );
}

export default ExportPdfButton;
