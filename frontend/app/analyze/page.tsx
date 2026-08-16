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
        que el resto de la app — no hay inferencia de un modelo de IA en vivo en este
        entorno, ver el detalle en el resultado.
      </p>
      <AnalyzeWizard />
    </>
  );
}
