/**
 * Los países cubiertos, en un solo lugar.
 *
 * Antes esta lista estaba repetida en seis archivos y en tres formas distintas
 * (`<option>`, mapa código→nombre, y objetos con moneda). Sumar Perú obligaba a
 * tocar los seis: olvidarse de uno no rompe el build ni ningún test, sólo deja
 * un país invisible en un filtro y no en otro. Cualquier país nuevo se agrega
 * acá y aparece en todas las pantallas a la vez.
 *
 * `currency` es la moneda en la que se guardan los montos de ese país
 * (`amount_original`). Sólo Costa Rica llega ya convertida a USD desde la
 * fuente; el resto se guarda en moneda nativa porque no hay una tasa de cambio
 * verificable por fecha.
 */

export type Country = {
  code: string;
  name: string;
  currency: string;
  /** Who publishes the data. Proper nouns, so they are not translated. */
  source: string;
};

export const COUNTRIES: Country[] = [
  { code: "PY", name: "Paraguay", currency: "PYG", source: "DNCP" },
  { code: "CO", name: "Colombia", currency: "COP", source: "SECOP II · datos.gov.co" },
  { code: "CR", name: "Costa Rica", currency: "CRC", source: "SICOP · Observatorio de Compra Pública" },
  { code: "DO", name: "República Dominicana", currency: "DOP", source: "DGCP" },
  { code: "PE", name: "Perú", currency: "PEN", source: "OECE · contrataciones abiertas" },
  // El Salvador esta dolarizado desde 2001: sus montos ya vienen en USD
  // desde la fuente, sin conversion de por medio.
  { code: "SV", name: "El Salvador", currency: "USD", source: "COMPRASAL · DINAC" },
  { code: "BR", name: "Brasil", currency: "BRL", source: "Compras.gov.br" },
  { code: "UY", name: "Uruguay", currency: "UYU", source: "ARCE · OCDS" },
];

/** Mapa código → nombre, para las pantallas que sólo necesitan etiquetar. */
export const COUNTRY_NAMES: Record<string, string> = Object.fromEntries(
  COUNTRIES.map((c) => [c.code, c.name]),
);
