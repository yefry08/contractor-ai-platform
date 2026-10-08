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
    slug: "el-1-por-ciento-que-se-lleva-casi-todo",
    title: "El 1% que se lleva casi todo: cuánto del gasto concentran los contratos más grandes",
    summary:
      "En República Dominicana un solo contrato de almuerzo escolar suma el 93% del monto de la muestra. En Paraguay el contrato más grande no llega al 3%.",
    tags: ["Concentración", "Gasto"],
    countries: ["PY", "CO", "CR", "DO", "PE", "SV", "BR", "UY", "CL", "GT"],
    minutes: 4,
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
    slug: "dos-modelos-un-contrato",
    title: "Dos modelos, un contrato: cuándo coinciden el modelo de IA de Daniel Duque y la estadística",
    summary:
      "En Paraguay el modelo BERT + XGBoost marca 696 contratos y la capa estadística 231, pero solo 62 coinciden. Por qué eso es una buena noticia y por dónde empezar a mirar.",
    tags: ["Modelos", "IA"],
    countries: ["PY", "CO"],
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
    slug: "el-efecto-diciembre",
    title: "El efecto diciembre: ¿se gasta a las apuradas al cierre del año fiscal?",
    summary: "Paraguay (2014–2022) y Uruguay tienen años completos para medir si el gasto se acelera en las últimas semanas.",
    tags: ["Estacionalidad"],
    countries: ["PY", "UY"],
    status: "soon",
    needs: "Años completos para más países; hoy la mayoría cubre uno o dos meses.",
  },
  {
    slug: "contratos-en-fin-de-semana",
    title: "Contratos adjudicados en sábado y domingo",
    summary: "Costa Rica registra 132 adjudicaciones en fin de semana. ¿Urgencias, cargas tardías o procesos acelerados?",
    tags: ["Fechas", "Procesos"],
    countries: ["CR", "CO", "PY"],
    status: "soon",
    needs: "Distinguir la fecha de adjudicación de la fecha de publicación en cada portal.",
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
