import { AnalyzeWizard } from "@/components/analyze-wizard";
import { AnalyzeOnboarding } from "@/components/analyze-onboarding";
import { getServerT } from "@/lib/i18n-server";

export const metadata = {
  title: "Analizar un contrato — Contractor AI",
};

export default async function AnalyzePage() {
  const { t } = await getServerT();

  return (
    <>
      <a href="/" className="wizard-back">
        ← {t("common.backHome")}
      </a>
      <h1>{t("analyze.title")}</h1>
      <p className="subtitle">{t("analyze.lead")}</p>

      <AnalyzeOnboarding />

      <AnalyzeWizard />
    </>
  );
}
