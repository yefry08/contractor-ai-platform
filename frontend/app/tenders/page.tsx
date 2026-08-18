import { listTenderCategories, listTenderPortals } from "@/lib/api";
import { TenderCountryCard } from "@/components/tender-country-card";

export default async function TendersPage() {
  const portals = await listTenderPortals();
  const categoriesByCountry = await Promise.all(
    portals.map((p) => listTenderCategories(p.country_code)),
  );

  return (
    <>
      <h1>Preparate para ofertar</h1>
      <p className="subtitle">
        Elegí un país y una categoría para ver el precio mediano y el rango típico de
        contratos similares ya adjudicados — una referencia para armar una oferta
        competitiva, no una garantía de adjudicación. Después, el enlace te lleva al
        portal oficial de cada país para ver las licitaciones abiertas y postular de
        verdad ahí.
      </p>

      <div className="note">
        Esto no es un listado de licitaciones abiertas en vivo ni un canal de postulación:
        Contractor AI todavía no tiene un scraper conectado a los portales oficiales.
        Lo que sí podemos ofrecer, con datos ya ingeridos, es el precio de referencia — y
        un enlace directo y verificado al portal real de cada país para postular.
      </div>

      <div className="tender-grid">
        {portals.map((portal, i) => (
          <TenderCountryCard key={portal.country_code} portal={portal} categories={categoriesByCountry[i]} />
        ))}
      </div>
    </>
  );
}
