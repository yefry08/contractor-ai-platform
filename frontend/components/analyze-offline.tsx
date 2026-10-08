import { getServerT } from "@/lib/i18n-server";

const MODEL_URL = "https://huggingface.co/ElDoctor/contractor-ai-latam";
const SPACE_URL = "https://huggingface.co/spaces/ElDoctor/contractor-ai-analizador";

const SNIPPET = `pip install huggingface_hub
python -c "from huggingface_hub import snapshot_download as d; print(d('ElDoctor/contractor-ai-latam'))"
# entra a la carpeta que imprimió y:
python analyzer.py --country GT --amount 89500`;

/** Where to run the same comparison without this site: the Hugging Face Space,
 *  the offline analyzer, and Daniel Duque's original model. */
export async function AnalyzeOffline() {
  const { t } = await getServerT();

  return (
    <section className="offline" id="fuera-de-la-plataforma">
      <h2 className="wizard-subtitle">{t("offline.title")}</h2>
      <p className="wizard-note" style={{ marginBottom: 16 }}>
        {t("offline.lead")}
      </p>

      <div className="offline-grid">
        <a className="card offline-card" href={SPACE_URL} target="_blank" rel="noopener noreferrer">
          <span className="offline-icon" aria-hidden="true">🌐</span>
          <h3>{t("offline.spaceTitle")}</h3>
          <p>{t("offline.spaceText")}</p>
          <span className="offline-cta">{t("offline.spaceCta")} ↗</span>
        </a>

        <div className="card offline-card">
          <span className="offline-icon" aria-hidden="true">💻</span>
          <h3>{t("offline.localTitle")}</h3>
          <p>{t("offline.localText")}</p>
          <pre className="offline-code">
            <code>{SNIPPET}</code>
          </pre>
          <a className="offline-cta" href={MODEL_URL} target="_blank" rel="noopener noreferrer">
            {t("offline.localCta")} ↗
          </a>
        </div>

        <a className="card offline-card" href={`${MODEL_URL}/tree/main/bert-xgboost`} target="_blank" rel="noopener noreferrer">
          <span className="offline-icon" aria-hidden="true">🧠</span>
          <h3>{t("offline.baseTitle")}</h3>
          <p>{t("offline.baseText")}</p>
          <span className="offline-cta">{t("offline.baseCta")} ↗</span>
        </a>
      </div>
    </section>
  );
}
