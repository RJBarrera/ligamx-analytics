import html2canvas from "html2canvas";
import { jsPDF } from "jspdf";

// Utilidades
const esperar = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const limpiarNombreArchivo = (texto = "") => {
  return String(texto)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9-_]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-+|-+$/g, "");
};

const obtenerFechaArchivo = () => {
  const fecha = new Date();
  const year = fecha.getFullYear();
  const month = String(fecha.getMonth() + 1).padStart(2, "0");
  const day = String(fecha.getDate()).padStart(2, "0");

  return `${year}-${month}-${day}`;
};

// Capturar Elemento
const capturarElemento = async (element) => {
  const canvas = await html2canvas(element, {
    // Mejor resolución
    scale: 2,
    useCORS: true,
    allowTaint: false,
    logging: false,
    backgroundColor: "#f4f7fb",
    scrollX: 0,
    scrollY: -window.scrollY,
    windowWidth: document.documentElement.scrollWidth,
    windowHeight: document.documentElement.scrollHeight,
    imageTimeout: 15000,
    removeContainer: true,
  });

  return canvas;
};

// Footer PDF
const agregarFooters = (pdf, local, visitante) => {
  const totalPaginas = pdf.getNumberOfPages();
  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();

  for (let pagina = 1; pagina <= totalPaginas; pagina += 1) {
    pdf.setPage(pagina);

    // Línea inferior
    pdf.setDrawColor(220, 227, 235);
    pdf.setLineWidth(0.25);
    pdf.line(10, pageHeight - 8, pageWidth - 10, pageHeight - 8);

    // Texto izquierdo
    pdf.setFont("helvetica", "normal");
    pdf.setFontSize(7);
    pdf.setTextColor(115, 128, 146);
    pdf.text(`MatchLab | ${local} vs ${visitante}`, 10, pageHeight - 4.5);

    // Página
    pdf.text(
      `Pagina ${pagina} de ${totalPaginas}`,
      pageWidth - 10,
      pageHeight - 4.5,
      {
        align: "right",
      },
    );
  }
};

// Exportar Reporte
export const exportMatchReport = async ({ element, local, visitante }) => {
  if (!element) {
    throw new Error("No se encontró el contenido del reporte.");
  }

  // Esperar Fuentes
  if (document.fonts?.ready) {
    await document.fonts.ready;
  }

  // Modo PDF
  element.classList.add("match-results--pdf-export");

  try {
    // Eséramos la carga de renderizado de Recharts
    await esperar(350);
    await new Promise((resolve) =>
      requestAnimationFrame(() => requestAnimationFrame(resolve)),
    );

    // PDF A4 Horizontal
    const pdf = new jsPDF({
      orientation: "landscape",
      unit: "mm",
      format: "a4",
      compress: true,
    });

    const pageWidth = pdf.internal.pageSize.getWidth();
    const pageHeight = pdf.internal.pageSize.getHeight();

    // Márgenes
    const marginX = 8;
    const marginTop = 8;
    const marginBottom = 13;
    const gap = 4;
    const contentWidth = pageWidth - marginX * 2;
    const maxPageHeight = pageHeight - marginTop - marginBottom;
    let currentY = marginTop;
    let primeraImagen = true;

    // Captura hijos del resultado (Todo lo dentro de .match-results)
    const sections = Array.from(element.children).filter(
      (child) => child.dataset?.pdfIgnore !== "true",
    );

    if (sections.length === 0) {
      throw new Error("No hay secciones disponibles para exportar.");
    }

    // Procesar Secciones
    for (const section of sections) {
      const canvas = await capturarElemento(section);

      if (!canvas.width || !canvas.height) {
        continue;
      }

      const imageData = canvas.toDataURL("image/png", 1.0);

      // Dimensiones
      let imageWidth = contentWidth;
      let imageHeight = (canvas.height * imageWidth) / canvas.width;

      // Por si una secci[on es más alta que una página]
      if (imageHeight > maxPageHeight) {
        const ratio = maxPageHeight / imageHeight;
        imageHeight = imageHeight * ratio;
        imageWidth = imageWidth * ratio;
      }

      // Nueva página si no cabe completa
      if (
        !primeraImagen &&
        currentY + imageHeight > pageHeight - marginBottom
      ) {
        pdf.addPage();
        currentY = marginTop;
      }

      // Centrar si fue necesario reducir
      const x = marginX + (contentWidth - imageWidth) / 2;

      // Agregar al PDF
      pdf.addImage(
        imageData,
        "PNG",
        x,
        currentY,
        imageWidth,
        imageHeight,
        undefined,
        "FAST",
      );

      currentY += imageHeight + gap;
      primeraImagen = false;
    }

    // Footers
    agregarFooters(pdf, local, visitante);

    // Nombre del archivo
    const localArchivo = limpiarNombreArchivo(local) || "Local";
    const visitanteArchivo = limpiarNombreArchivo(visitante) || "Visitante";
    const fecha = obtenerFechaArchivo();
    const nombre = `MatchLab_${localArchivo}_vs_${visitanteArchivo}_${fecha}.pdf`;

    // Descargar
    pdf.save(nombre);

    return {
      success: true,
      fileName: nombre,
    };
  } finally {
    // Restaurar Página
    element.classList.remove("match-results--pdf-export");
  }
};
