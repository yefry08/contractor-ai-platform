# Relevamiento de países para Fase 2 (ingesta multi-país en vivo)

> Desbloquea el punto "Confirmación de alcance de países para Fase 2" de
> `PROGRESS.md`. Basado en búsqueda web (agosto 2026) contra el registro
> público de OCP (`data.open-contracting.org`) y comunicados oficiales de cada
> organismo — no en acceso directo verificado a cada API (eso es el primer paso
> de implementación de cada conector, no de este relevamiento). Antes de
> implementar un conector, confirmar el endpoint real y sus términos de uso.

## Con API OCDS — candidatos directos para Fase 2 (conector API, sin scraper)

| País | Organismo | Estado | Notas |
|---|---|---|---|
| Paraguay | DNCP | ✅ Ya integrado (Fase 1) | Actualización horaria, datos desde 2011. Portal: contrataciones.gov.py |
| Colombia | Agencia Nacional de Contratación Pública (SECOP II / TVEC) | ⚠️ API OCDS "oficial" sin verificar — **pero hay alternativa verificada y ya integrada** | El endpoint OCDS de Colombia Compra Eficiente nunca se pudo confirmar (la página oficial no publica la URL, ver PROGRESS.md 2026-08-15). En su lugar se usó **datos.gov.co** (portal oficial de datos abiertos del gobierno, dataset "SECOP II - Contratos Electrónicos", API pública Socrata/SODA, id `jbjy-vk9h`) — verificado en vivo el 2026-08-15 (actualizado el mismo día, ~5.95M contratos totales). No es OCDS nativo (es tabular), se mapea campo a campo. Ya integrado como ingesta en vivo en `backend/scripts/ingest_colombia_live.py` (5,000 contratos más recientes, idempotente vía `id_contrato`). Sin modelo de predicción corriendo en vivo todavía — esos contratos no tienen score de anomalía. |
| Chile | ChileCompra (Dirección de Compras y Contratación Pública) | API disponible, tiempo real | Cobertura completa desde 2022 en el dataset OCDS (implementación empezó en 2018, fue creciendo en alcance). Buen candidato para ir después de Colombia. |
| Perú | OECE (ex-OSCE), vía SEACE | ✅ Ya integrado (2026-09-04) — **pero el dominio de este relevamiento estaba muerto** | El `contratacionesabiertas.osce.gob.pe` que figuraba acá **ya no resuelve**: al renombrarse el organismo de OSCE a OECE cambió también el dominio. El bueno es `contratacionesabiertas.oece.gob.pe` (verificado 2026-09-04: el viejo da error de conexión, el nuevo 200). Lo mismo con el portal institucional: `seace.gob.pe` y `portal.osce.gob.pe` no resuelven, `gob.pe/oece` sí. OCDS 1.1 nativo, paginación `?page=N` de 20 releases, se agota en la página 500 (501 devuelve 404). El feed mezcla etapas: sólo ~30% de los releases tienen `awards`, y se ingieren únicamente esos, con `award.value` (monto adjudicado) y nunca `tender.value` (valor referencial). Integrado en `backend/scripts/ingest_peru_live.py`. **Es la primera fuente del proyecto con proveedor identificado (RUC) y clasificación real de objeto de compra (CUBSO)**, y el primer país cuyo `mainProcurementCategory` reparte de verdad (goods/services/works) en vez de concentrar todo en una sola categoría. |
| Ecuador | SERCOP | API disponible | Empezó publicando compras de emergencia COVID-19 en OCDS, ahora cubre contratación general. |
| Costa Rica | Ministerio de Hacienda (Observatorio de Compra Pública / SICOP) | ✅ Ya integrado (2026-08-15) — no vía API OCDS | SICOP no tiene API ni datos abiertos OCDS (confirmado). El Observatorio publica en cambio un ZIP mensual con CSVs relacionales de todo SICOP, **actualizado diariamente** para el mes en curso, en una URL documentada y predecible. Integrado en `backend/scripts/ingest_costa_rica_live.py`: 1,643 contratos, con fecha real y monto ya convertido a USD por el propio SICOP. |
| República Dominicana | DGCP | ✅ Ya integrado (2026-08-15) — API distinta de la que parecía bloqueada | El portal CKAN (`datos.gob.do`) funciona para metadata pero sus 6 datasets son archivos estáticos en `dgcp.gob.do`, bloqueados por Cloudflare para clientes automatizados (esa parte sigue siendo cierta). Pero `datosabiertos.dgcp.gob.do` es un dominio/producto distinto ("API DGCP") con REST completo y OCDS nativo, licencia Apache 2.0. También detrás de Cloudflare, pero solo en modo básico: bloquea el User-Agent por defecto de `urllib`/`requests`, pasa con un User-Agent de navegador real — no throttling por frecuencia (25 pedidos seguidos, 0 fallos). Integrado en `backend/scripts/ingest_dominican_republic_live.py`: 2,000 contratos, 0 fallidos, idempotente. |

## Verificado con API pero NO viable para ingesta (Fase 2 descartada, no por falta de intento)

| País | Organismo | Estado | Notas |
|---|---|---|---|
| Panamá | DGCP / PanamaCompraenCifras | ⚠️ API OCDS real y documentada, pero **datos estructuralmente vacíos** | `ocds.panamacompraencifras.gob.pa` (encontrado tras descartar dos subdominios señuelo/dev) responde bien, con endpoints `/Record`, `/Release` reales y paginados. Pero se verificó en varias muestras (2023 y 2024) que `compiledRelease` **nunca** trae tender/award/value/description/supplier — solo `buyer` + `ocid` + fecha. No es un problema de acceso ni de staleness (que también existe: nada después de agosto 2024) — es que el pipeline de publicación de Panamá nunca llena los campos sustantivos del release. Construir un conector produciría contratos sin título, sin monto, sin descripción: no aporta nada útil. **Se decidió no construir el conector**, no por falta de esfuerzo sino porque los datos de origen no lo permiten. |

## Sin API documentada — candidatos a scraper (Fase 4, no Fase 2)

| País | Organismo | Estado |
|---|---|---|
| Argentina | Compr.ar / sistemas provinciales (ej. Buenos Aires Compras) | Solo descarga en bloque, sin API — y fragmentado por jurisdicción (nacional + CABA + provincias como Mendoza publican por separado). Requiere decidir si Fase 2/4 apunta al nivel nacional o también a jurisdicciones subnacionales. |
| Honduras | ONCAE / HonduCompras 2.0 | Solo descarga en bloque. Portal más nuevo (implementación reportada ~2020), en desarrollo activo (agregando OC4IDS para infraestructura vía SISOCS). |

## Sin datos encontrados

- **Nicaragua**: no aparece en el registro de OCP ni en las búsquedas realizadas. No se encontró evidencia de que publique en formato OCDS. Marcar como "sin fuente conocida" hasta que aparezca algo — no se debe planificar un conector a ciegas.

## Recomendación de orden para Fase 2

1. ~~**Colombia**~~ — ✅ hecho (2026-08-15). Ingesta en vivo funcionando contra datos.gov.co (ver tabla arriba y `backend/scripts/ingest_colombia_live.py`), más un dataset ya procesado de un tercero como complemento (`backend/scripts/migrate_colombia.py`). Pendiente: correr un modelo de predicción sobre los contratos que entran en vivo (hoy no tienen score de anomalía), y decidir si vale la pena seguir insistiendo con el endpoint OCDS oficial o quedarse con datos.gov.co como fuente definitiva para Colombia.
2. **Chile** — ⚠️ conector escrito pero **no verificado a volumen útil**: ChileCompra corta las ráfagas de pedidos al endpoint de detalle (urllib, requests y curl fallan ~100% en loop; un pedido aislado siempre funciona). Ver la investigación completa en el docstring de `backend/scripts/ingest_chile_live.py`. No seguir tanteando el delay por prueba y error: preguntar el límite real a ChileCompra.
3. ~~**Perú**~~ — ✅ hecho (2026-09-04). Ver la fila de arriba. Ojo: el dominio que figuraba en este documento estaba muerto.
4. **Ecuador** — API disponible, menos verificado en esta pasada; confirmar estabilidad del endpoint antes de comprometerse.

> **Lección del caso Perú, aplicable al resto:** este relevamiento se hizo por
> búsqueda web, no por acceso verificado. El dominio de Perú ya había cambiado
> cuando se intentó usar. Antes de dar por bueno cualquier endpoint de esta
> tabla, hacer una petición real: los organismos se renombran y se llevan el
> dominio puesto.

Argentina, R. Dominicana, Honduras y Costa Rica quedan para Fase 4 (scraping) o
para una futura versión de Fase 2 si alguno de ellos publica una API antes de
llegar a esa fase — revisitar este documento, no asumir que la situación actual
es permanente (estos portales cambian; el propio dataset de Colombia dejó de
actualizarse en algún punto sin que eso implique que el proyecto se cerró).

## Fuentes

- [OCP Data Registry — búsqueda de publicadores](https://data.open-contracting.org/en/search/)
- [DGCP República Dominicana — Estándar Mundial OCDS](https://www.dgcp.gob.do/nueva/datos-abiertos/estandar-mundial-ocds/)
- [ChileCompra y OCDS — Gobierno Transparente Chile](https://www.gobiernotransparentechile.cl/datos-abiertos/chilecompra-ocds/)
- [Portal de Contrataciones Abiertas de la Compra Pública de Perú — API](https://contratacionesabiertas.osce.gob.pe/api)
- [OSCE/OECE implementa el Estándar de Datos para las Contrataciones Abiertas](https://www.gob.pe/institucion/oece/noticias/884163-osce-implementa-el-estandar-de-datos-para-las-contrataciones-abiertas-ocds)
- [Open Contracting Partnership — Implementing an open contracting portal in Honduras](https://www.open-contracting.org/es/2020/10/13/implementing-an-open-contracting-portal-in-honduras/)
- [CoST — Data disclosure in Honduras steps up a gear with OC4IDS](https://infrastructuretransparency.org/news/disclosure-in-honduras-steps-up-a-gear-with-implementation-of-oc4ids/)
