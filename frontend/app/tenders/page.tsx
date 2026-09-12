import { listTenderCategories, listTenderPortals } from "@/lib/api";
import { TenderCountryCard } from "@/components/tender-country-card";
import { getServerT } from "@/lib/i18n-server";

export default async function TendersPage() {
  const [portals, { t }] = await Promise.all([listTenderPortals(), getServerT()]);
  const categoriesByCountry = await Promise.all(
    portals.map((p) => listTenderCategories(p.country_code)),
  );

  return (
    <>
      <h1>{t("tenders.title")}</h1>
      <p className="subtitle">{t("tenders.lead")}</p>

      <div className="note">{t("tenders.note")}</div>

      <div className="tender-grid">
        {portals.map((portal, i) => (
          <TenderCountryCard key={portal.country_code} portal={portal} categories={categoriesByCountry[i]} />
        ))}
      </div>
    </>
  );
}
