import { AnalyzeWizard } from "@/components/analyze-wizard";

export const metadata = {
  title: "Analizar un contrato — Contractor AI",
};

export default function AnalyzePage() {
  return (
    <>
      <a href="/" className="wizard-back">
        ← Volver al inicio
      </a>
      <h1>Analizar un contrato</h1>
      <p className="subtitle">
        Subí el documento en el formato que tengas. Lo comparamos contra contratos ya
        ingeridos del país que elijas, usando la misma capa estadística (mediana + MAD)
        que el resto de la app — el veredicto es 100% estadístico, sin IA de por medio.
        Un resumen en lenguaje natural generado por IA está disponible como paso
        opcional al final, ver el detalle en el resultado.
      </p>
      <AnalyzeWizard />
    </>
  );
}
