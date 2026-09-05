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
};

export const COUNTRIES: Country[] = [
  { code: "PY", name: "Paraguay", currency: "PYG" },
  { code: "CO", name: "Colombia", currency: "COP" },
  { code: "CR", name: "Costa Rica", currency: "CRC" },
  { code: "DO", name: "República Dominicana", currency: "DOP" },
  { code: "PE", name: "Perú", currency: "PEN" },
];

/** Mapa código → nombre, para las pantallas que sólo necesitan etiquetar. */
export const COUNTRY_NAMES: Record<string, string> = Object.fromEntries(
  COUNTRIES.map((c) => [c.code, c.name]),
);
