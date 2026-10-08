/**
 * "Datos de los datos": studies run on the contracts Contractor AI ingests.
 *
 * Published posts quote frontend/content/datos/snapshot.json, built by
 * backend/scripts/build_datos_snapshot.py; a post never carries a number the
 * script doesn't produce. Upcoming posts are listed so readers can see what
 * is being worked on, and each says what data it still needs.
 *
 * Posts are written in Spanish; the index and the page chrome are translated.
 */

export type Post = {
  slug: string;
  title: string;
  summary: string;
  tags: string[];
  countries: string[];
  minutes?: number;
  /** Published posts have a body; upcoming ones say what they still need. */
  status: "published" | "soon";
  needs?: string;
};

export const POSTS: Post[] = [
  {
    slug: "el-techo-de-las-compras-directas",
    title: "El techo de las compras directas: 1.082 contratos de Guatemala se apiñan justo debajo de Q90.000",
    summary:
      "En Guatemala, una de cada cinco compras de la muestra cae entre Q88.000 y Q90.000, el máximo legal de la compra directa. República Dominicana muestra el mismo corte en su umbral de RD$268.111.",
    tags: ["Umbrales", "Fraccionamiento"],
    countries: ["GT", "DO"],
    minutes: 5,
    status: "published",
  },
  {
    slug: "ley-de-benford-en-10-paises",
    title: "La ley de Benford en 43.477 contratos: qué países se salen de la curva y por qué",
    summary:
      "Uruguay, Brasil y Chile siguen la distribución esperada de primeros dígitos. Guatemala, Colombia y República Dominicana se apartan, y cada desvío tiene una explicación distinta.",
    tags: ["Benford", "Calidad de datos"],
    countries: ["PY", "CO", "CR", "DO", "PE", "SV", "BR", "UY", "CL", "GT"],
    minutes: 6,
    status: "published",
  },
  {
    slug: "sobrecosto-o-subcosto",
    title: "¿Sobrecosto o subcosto? En Guatemala y Chile la mayoría de las alertas apuntan hacia abajo",
    summary:
      "Paraguay y Colombia marcan sobre todo contratos caros. Guatemala y Chile marcan sobre todo contratos baratísimos, y en Chile la mitad cuesta menos de CLP 1.000: más un problema de carga que de precio.",
    tags: ["Anomalías", "Calidad de datos"],
    countries: ["PY", "CO", "CR", "DO", "PE", "SV", "BR", "UY", "CL", "GT"],
    minutes: 5,
    status: "published",
  },
  {
    slug: "contratos-en-fin-de-semana",
    title: "Contratos adjudicados en sábado y domingo",
    summary:
      "Costa Rica registra 132 adjudicaciones en fin de semana, y 126 caen en solo dos fechas. En 6 de 8 países, una sola fecha reúne la mayor parte de los contratos de fin de semana: más una carga en bloque que una urgencia.",
    tags: ["Fechas", "Procesos"],
    countries: ["CR", "CO", "PY", "GT", "BR", "CL", "DO", "UY"],
    minutes: 5,
    status: "published",
  },
  {
    slug: "el-efecto-diciembre",
    title: "El efecto diciembre: ¿se gasta a las apuradas al cierre del año fiscal?",
    summary:
      "En Paraguay no hay un efecto diciembre estable: hasta 2018 el cierre de año es más flojo que el resto, y desde 2019 sube, con noviembre como el mes fuerte. Uruguay no se puede leer.",
    tags: ["Estacionalidad"],
    countries: ["PY", "UY"],
    minutes: 5,
    status: "published",
  },
  {
    slug: "montos-redondos",
    title: "¿Quién redondea? Montos escritos con una o dos cifras significativas",
    summary:
      "Un contrato de exactamente 150.000.000 suele ser un presupuesto estimado, no un precio de mercado. Colombia (33%) y Paraguay (29%) encabezan la lista preliminar.",
    tags: ["Montos", "Presupuesto"],
    countries: ["CO", "PY", "GT"],
    status: "soon",
    needs: "Separar el monto estimado del adjudicado en cada país antes de comparar.",
  },
  {
    slug: "concentracion-de-proveedores-peru",
    title: "Concentración de proveedores en Perú: el índice HHI por entidad",
    summary: "Perú es la única fuente que publica el proveedor adjudicado. ¿Cuántas entidades compran casi siempre al mismo?",
    tags: ["Proveedores", "Competencia"],
    countries: ["PE"],
    status: "soon",
    needs: "Ingerir más meses de Perú: hoy hay 85 contratos, pocos para medir concentración.",
  },
  {
    slug: "compradores-con-precios-dispersos",
    title: "Las instituciones con precios más dispersos",
    summary: "Qué compradores pagan montos muy distintos por la misma categoría, medido con la MAD de cada institución.",
    tags: ["Compradores", "Precios"],
    countries: ["PY", "CO", "CL", "DO"],
    status: "soon",
    needs: "Una categoría homogénea por país (UNSPSC) para comparar compras equivalentes.",
  },
];

export const postBySlug = (slug: string) => POSTS.find((p) => p.slug === slug);
