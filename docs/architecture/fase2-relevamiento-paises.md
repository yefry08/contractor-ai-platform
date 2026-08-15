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
| Colombia | Agencia Nacional de Contratación Pública (SECOP II / TVEC) | API disponible | **Ojo:** el registro de OCP muestra el dataset sin actualizar desde abril 2022 — verificar si el organismo sigue publicando OCDS activamente o si cambió de canal antes de construir el conector. |
| Chile | ChileCompra (Dirección de Compras y Contratación Pública) | API disponible, tiempo real | Cobertura completa desde 2022 en el dataset OCDS (implementación empezó en 2018, fue creciendo en alcance). Buen candidato para ir después de Colombia. |
| Perú | OECE (ex-OSCE), vía SEACE | API disponible (`contratacionesabiertas.osce.gob.pe/api`) | Dataset con mayor profundidad histórica (desde 2003). Fuente reporta problemas de calidad conocidos (IDs de organización duplicados, estados de contrato faltantes) — reforzar la validación de esquema por país (§5 riesgo #1 de PLANNING.md) especialmente aquí. |
| Ecuador | SERCOP | API disponible | Empezó publicando compras de emergencia COVID-19 en OCDS, ahora cubre contratación general. |

## Sin API documentada — candidatos a scraper (Fase 4, no Fase 2)

| País | Organismo | Estado |
|---|---|---|
| Argentina | Compr.ar / sistemas provinciales (ej. Buenos Aires Compras) | Solo descarga en bloque, sin API — y fragmentado por jurisdicción (nacional + CABA + provincias como Mendoza publican por separado). Requiere decidir si Fase 2/4 apunta al nivel nacional o también a jurisdicciones subnacionales. |
| República Dominicana | DGCP | Solo descarga en bloque (JSON/Excel/CSV trimestral), sin API. Cobertura 2018–2020 en lo verificado; confirmar si extendieron el rango. |
| Honduras | ONCAE / HonduCompras 2.0 | Solo descarga en bloque. Portal más nuevo (implementación reportada ~2020), en desarrollo activo (agregando OC4IDS para infraestructura vía SISOCS). |
| Costa Rica | (organismo por confirmar) | Listado como implementador activo de OCDS en fuentes de 2017, pero no se encontró documentación reciente de API ni de portal. Requiere verificación directa antes de clasificar. |

## Sin datos encontrados

- **Nicaragua**: no aparece en el registro de OCP ni en las búsquedas realizadas. No se encontró evidencia de que publique en formato OCDS. Marcar como "sin fuente conocida" hasta que aparezca algo — no se debe planificar un conector a ciegas.

## Recomendación de orden para Fase 2

1. **Colombia** — ya hay trabajo previo del equipo (`Code/main_colombia.ipynb`, datos en `Data/resultados finales/resultadoscol.xlsx`), aunque hay que confirmar primero si el organismo sigue publicando OCDS activamente (ver tabla).
2. **Chile** — API en tiempo real, buena documentación pública, sin señales de discontinuación.
3. **Perú** — mayor volumen histórico, pero exige más trabajo de limpieza por los problemas de calidad ya reportados por terceros.
4. **Ecuador** — API disponible, menos verificado en esta pasada; confirmar estabilidad del endpoint antes de comprometerse.

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
