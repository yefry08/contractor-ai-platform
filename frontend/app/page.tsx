import { COUNTRIES } from "@/lib/countries";
import { listContracts, ContractSummary } from "@/lib/api";
import { Hero } from "@/components/hero";
import { Metrics } from "@/components/metrics";
import { HowItWorks } from "@/components/how-it-works";
import { CountrySources } from "@/components/country-sources";
import { Team } from "@/components/team";
import { Partners } from "@/components/partners";
import { getServerT } from "@/lib/i18n-server";

function fmtUsd(n: number | null, locale: string) {
  if (n === null) return "—";
  return n.toLocaleString(locale, { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

function fmtAmount(c: ContractSummary, locale: string) {
  if (c.amount_usd !== null) return fmtUsd(c.amount_usd, locale);
  if (c.amount_original !== null && c.currency) {
    return `${c.amount_original.toLocaleString(locale)} ${c.currency}`;
  }
  return "—";
}

export default async function ContractsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;
  const limit = 5;
  const offset = Number(sp.offset ?? 0);

  const country = sp.country ?? "";
  const [data, { t, locale }] = await Promise.all([
    listContracts({
      country: country || undefined,
      buyer: sp.buyer,
      category: sp.category,
      only_anomalous: sp.only_anomalous === "1",
      limit,
      offset,
    }),
    getServerT(),
  ]);

  return (
    <>
      <Hero />
      <Metrics totalContracts={data.total} />
      <HowItWorks />

      <h1>{t("home.title")}</h1>
      <p className="subtitle">
        {t("home.subtitle", {
          n: data.total.toLocaleString(locale),
          countries: COUNTRIES.map((c) => c.name).join(", "),
        })}
      </p>

      <form className="filters" method="get">
        <select name="country" defaultValue={country}>
          <option value="">{t("home.allCountries")}</option>
          {COUNTRIES.map((c) => (
            <option key={c.code} value={c.code}>
              {c.name}
            </option>
          ))}
        </select>
        <input type="text" name="buyer" placeholder={t("home.searchBuyer")} defaultValue={sp.buyer ?? ""} />
        <input type="text" name="category" placeholder={t("home.searchCategory")} defaultValue={sp.category ?? ""} />
        <label style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--muted)" }}>
          <input type="checkbox" name="only_anomalous" value="1" defaultChecked={sp.only_anomalous === "1"} />
          {t("home.onlyAnomalous")}
        </label>
        <button type="submit">{t("home.filter")}</button>
      </form>

      <table>
        <thead>
          <tr>
            <th>{t("home.colTitle")}</th>
            <th>{t("home.colCountry")}</th>
            <th>{t("home.colBuyer")}</th>
            <th>{t("home.colCategory")}</th>
            <th>{t("home.colAmount")}</th>
            <th>{t("home.colDate")}</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((c) => (
            <tr key={c.id}>
              <td>
                <a href={`/contracts/${c.id}`}>{c.title ?? t("common.untitled")}</a>
              </td>
              <td>{c.country_code}</td>
              <td>{c.buyer?.name ?? "—"}</td>
              <td>{c.category_code ?? "—"}</td>
              <td>{fmtAmount(c, locale)}</td>
              <td>{c.award_date ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="pagination">
        {offset > 0 && (
          <a href={`?${new URLSearchParams({ ...sp, offset: String(Math.max(0, offset - limit)) } as Record<string, string>)}`}>
            ← {t("common.previous")}
          </a>
        )}
        <span>
          {offset + 1}–{Math.min(offset + limit, data.total)} {t("common.of")} {data.total.toLocaleString(locale)}
        </span>
        {offset + limit < data.total && (
          <a href={`?${new URLSearchParams({ ...sp, offset: String(offset + limit) } as Record<string, string>)}`}>
            {t("common.next")} →
          </a>
        )}
      </div>

      <CountrySources />
      <Team />
      <Partners />
    </>
  );
}
