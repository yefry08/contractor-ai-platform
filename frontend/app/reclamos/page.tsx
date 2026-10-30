import { InquiryForm } from "@/components/inquiry-form";
import { InquiryLookup } from "@/components/inquiry-lookup";
import { getServerT } from "@/lib/i18n-server";

export const metadata = {
  title: "Consultas y reclamos — Contractor AI",
  description:
    "Haz una consulta o un reclamo sobre un proceso de contratación pública en América Latina y encuentra el canal oficial para presentarlo.",
};

export default async function ReclamosPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;
  const { t } = await getServerT();

  return (
    <>
      <p className="datos-eyebrow">{t("inq.eyebrow")}</p>
      <h1 className="datos-title">{t("inq.title")}</h1>
      <p className="subtitle datos-lead">{t("inq.lead")}</p>

      <div className="inq-layout">
        <InquiryForm
          initial={{
            kind: sp.tipo,
            country: sp.pais,
            process: sp.proceso,
            institution: sp.institucion,
            opportunityId: sp.op,
            contractId: sp.contrato,
          }}
        />
        <aside className="inq-side">
          <div className="card">
            <h2 className="wizard-subtitle" style={{ marginTop: 0 }}>
              {t("inq.whatHappensTitle")}
            </h2>
            <ol className="inq-steps">
              <li>{t("inq.step1")}</li>
              <li>{t("inq.step2")}</li>
              <li>{t("inq.step3")}</li>
            </ol>
            <p className="note">{t("inq.notLegal")}</p>
          </div>
          <InquiryLookup />
        </aside>
      </div>
    </>
  );
}
