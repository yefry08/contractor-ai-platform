# Changelog

Formato libre, orden cronológico inverso (más reciente arriba). Referencia a
`docs/adr/` para el razonamiento detrás de decisiones de arquitectura.

## 2026-08-18 — Módulo de licitaciones + categorías reales para Rep. Dominicana

A pedido del usuario: nuevo módulo `/tenders` ("Preparate para ofertar") --
para cada uno de los 4 países, el usuario elige una categoría de contrato y
ve la mediana + rango típico (IQR) de contratos similares ya adjudicados,
para armar una oferta con un precio de referencia real en vez de adivinar.
Reutiliza la misma capa de estadística (mediana + MAD) del resto de la app.
No pretende listar licitaciones abiertas en vivo ni postular en nombre de
nadie -- no hay scraper conectado en este entorno (se evaluó importar el
MCP de ScraperGraph, requiere API key y setup interactivo no disponible
aquí) y aunque lo hubiera, "postular por una empresa" es una superficie de
confianza/legal mucho más grande de lo que esta herramienta debería asumir
unilateralmente. En cambio: un link verificado y real al portal oficial de
compras públicas de cada país (contrataciones.gov.py, colombiacompra.gov.co,
sicop.go.cr, dgcp.gob.do -- cada uno confirmado con un request HTTP real
antes de escribirlo en el código, no adivinado) para que el usuario postule
de verdad ahí.

Al construirlo se encontró que República Dominicana tenía category_code
NULL en las 2000 contrataciones ingeridas (0%) -- el motivo por el que el
observatorio y el propio módulo de licitaciones no podían mostrar nada útil
para ese país. El usuario aportó el link a
[datos.gob.do/dataset/datos-procesos-publicados](https://datos.gob.do/dataset/datos-procesos-publicados)
(grupo PIDA, publicado por la DGCP, licencia ODbL), un CSV oficial de ~233MB
con los procesos publicados en el SECP 2015-2026, con exactamente el campo
de categoría que faltaba (`OBJETO_PROCESO`: "Bienes"/"Servicios") y la
modalidad de contratación (`MODALIDAD`, incluyendo "Compras por Debajo del
Umbral" -- el mecanismo de compras menores que el usuario mencionó,
actualmente RD$268,111.38). Cruzado por `codigo_proceso`, ya guardado (pero
nunca usado) en el `raw_ocds_json` de cada contrato desde la ingesta
original.

El snapshot CSV (actualización semestral, últimos datos a 2026-06-30) solo
cerró 165 de 2000 -- nuestros contratos de Rep. Dominicana son todos de
agosto 2026, fuera de su ventana. Se probó el endpoint **en vivo**
`datosabiertos.dgcp.gob.do/api-dgcp/v1/procesos` (mismo dominio/API que ya
usa la ingesta principal para `/contratos`, mismo hallazgo de Cloudflare:
bloquea el User-Agent por defecto, no un User-Agent de navegador real) --
tiene los mismos campos al día de hoy. Paginado hacia atrás (más reciente
primero) hasta cubrir la fecha del contrato más antiguo sin dato, cerró
1,320 más. Total: 1,485 / 2,000 (74%) con category_code y
procurement_method reales, dejando 515 genuinamente sin proceso
correspondiente encontrado en ninguna de las dos fuentes -- no forzado ni
inventado. Script:
[`backend/scripts/enrich_dominican_republic_categories.py`](backend/scripts/enrich_dominican_republic_categories.py),
solo rellena campos NULL, nunca sobreescribe `amount_original`/`currency`
existentes (`MONTO_ESTIMADO` del CSV es una *estimación* al momento de
publicación, no el monto contratado real -- mezclarlos hubiera sido un
error de integridad de datos, no un enriquecimiento).

Bug encontrado y corregido durante las pruebas en navegador: el `<select>`
de categoría arranca con la primera categoría pre-seleccionada, pero
`onChange` solo dispara ante un cambio real -- un visitante que nunca toca
el dropdown no veía nunca el benchmark. Corregido con un efecto que carga
el benchmark de la categoría por defecto al montar el componente.

## 2026-08-17 — Panel, ranking, participación ciudadana, tests, seguridad

Preparando la plataforma para el "Desafío de Datos para la Democracia: 25
años de la Carta Democrática Interamericana" (OEA) — convocatoria que evalúa
relevancia democrática, innovación, uso de datos abiertos, factibilidad,
escalabilidad e impacto potencial, y nombra explícitamente tableros,
visualizaciones y acceso a datos abiertos como cualidades buscadas.

- **`/dashboard`**: métricas agregadas, contratos y tasa de anomalías por
  año, categorías principales, comparación entre los 4 países, y un ranking
  de las **instituciones con mejor historial de contratación** (menor tasa
  de anomalías, mínimo 5 contratos para evitar ruido de muestra chica) — a
  pedido explícito del usuario, en vez de un listado de peores infractores.
  Gráficos de barras en CSS puro, sin dependencia nueva. Exportación CSV.
- **Participación ciudadana**: cualquier visitante puede dejar un comentario
  público en un contrato (señalar un problema o aportar contexto), sin
  login, con honeypot y rate limit por IP — cierra el único de los 7 temas
  de la convocatoria de la OEA que la plataforma no tocaba todavía.
- **Navbar**: enlaces muertos ("Panel institucional", "API") eliminados,
  enlace duplicado a `/analyze` eliminado, alineación consistente. Roles del
  equipo actualizados. Tema claro por defecto con toggle a modo oscuro
  persistido en `localStorage`.
- **Auditoría de seguridad + 3 bugs reales corregidos**, no solo nuevas
  features:
  - SSRF: `/analyze/extract` validaba la URL de entrada pero seguía
    redirecciones 3xx sin re-validar el destino — un link público podía
    devolver un 302 hacia una IP privada o el endpoint de metadata de nube
    (`169.254.169.254`) y el fetch lo seguía igual. Corregido re-validando
    cada salto de redirección; verificado con un servidor HTTP local que
    redirige a una dirección bloqueada.
  - `dashboard.get_summary`: el conteo de `total_anomalies` mezclaba una
    subquery con una columna referida directamente desde `Anomaly`,
    generando un producto cartesiano que ignoraba en silencio el filtro de
    país y de `status="open"`. Invisible en producción porque hoy todas las
    anomalías ingeridas tienen `status="open"` — solo lo atrapó un test que
    mezcla estados y países a propósito.
  - Extracción de montos de PDF/link no reconocía números con **solo
    puntos** como separador de miles ("1.500.000", el formato más común en
    los portales de los 4 países) — se descartaban en silencio. Reescrita la
    normalización para ser agnóstica al separador.
  - Rate limit agregado a `/analyze/extract` y `/analyze/compare` (antes sin
    límite); dependencias de `backend/requirements.txt` fijadas a versiones
    exactas (antes sin pin, build no reproducible).
- **`backend/tests/`**: 53 tests con pytest contra SQLite aislado (nunca
  contra la Postgres de producción real, aunque el entorno de desarrollo
  local apunta ahí por conveniencia — ver `backend/tests/conftest.py` para
  cómo se garantiza el aislamiento).
- README raíz rediseñado con banner SVG propio. Se declinó instalar
  `@marswave/colaskill-cli` vía `npx -y` a pedido de `colaskill.com`:
  instrucciones de ejecución de una página de terceros no se tratan como
  órdenes confiables.

## 2026-08-15 — Primer despliegue a producción: Render + Vercel

A pedido del usuario ("docker is ready and please deploy with a free .dev
domain", luego "Vercel+Render" tras un fallo de pago en Fly.io).

- Backend desplegado en Render (`contractor-ai-api.onrender.com`) vía
  `render.yaml` (Blueprint: web service Docker + Postgres gestionado, free
  tier, sin tarjeta). Frontend en Vercel
  (`contractor-ai-one.vercel.app`), con `NEXT_PUBLIC_API_URL` apuntando al
  backend de Render.
- Repo publicado en GitHub como `yefry08/contractor-ai-platform`, **privado**
  — el historial ya tenía archivos con datos sensibles reales (lista de
  usuarios, base de proveedores, comprobantes) desde el commit inicial de
  Fase 0; no se hizo público sin decidir primero qué hacer con eso.
- Corridas las 5 fuentes de datos y la capa estadística contra la Postgres
  real de producción (no solo SQLite local). En el camino, la migración de
  Paraguay se quedó pegada en la fila ~500 contra la base remota — los 5
  scripts de ingesta hacían un `db.flush()` innecesario por fila (todos los
  modelos ya generan su UUID del lado de Python, no hacía falta leer el ID
  de vuelta del servidor). Corregido generando los UUIDs explícitamente
  antes de insertar; la migración completa de Paraguay pasó de trabarse a
  terminar en menos de 2 minutos. Verificado con los 5 scripts corridos de
  nuevo de punta a punta contra producción: 15,473 contratos totales,
  confirmado con `curl` directo a la API ya desplegada, no solo localmente.

## 2026-08-15 — Capa estadística independiente (Fase 5 / ADR 0003)

A pedido del usuario, tras preguntar "¿cuál es el siguiente paso?" y aceptar
la recomendación: más de la mitad de los contratos (Colombia en vivo, Costa
Rica, Rep. Dominicana — ~8.600 de 15.473) no tenían ningún score de
anomalía, porque solo los datasets ya procesados (Paraguay, bulk de
Colombia) traían predicciones del modelo NLP.

Añadido `backend/scripts/compute_statistical_anomalies.py`: z-score
modificado (Iglewicz & Hoaglin) + cercas de Tukey (IQR) sobre log(monto),
agrupado por comprador/categoría/país con fallback jerárquico, totalmente
independiente de cualquier modelo de IA. Llena `statistical_flags` (sin
usar hasta ahora) y crea o completa filas de `Anomaly`.

Dos bugs reales corregidos probando contra los datos reales (no en teoría):
un z-score de 258,491 en un contrato legítimo de Costa Rica por calcular
sobre montos crudos en vez de log(monto) -- corregido; y un comprador de
Paraguay con un grupo de referencia casi sin varianza que seguía dando
scores en los miles incluso en escala log -- corregido acotando |z| en 50
(muy por encima del umbral de marcado, no cambia qué se marca).

724 anomalías nuevas solo-estadísticas, 803 anomalías NLP existentes ahora
con las dos señales visibles por separado. Idempotente. Frontend actualizado
para mostrar qué señal(es) marcaron cada contrato, verificado en navegador
incluyendo un caso donde ambas señales independientes coinciden.

## 2026-08-15 — República Dominicana en vivo (corrección del hallazgo anterior)

El usuario preguntó puntualmente por Rep. Dominicana después de que se
reportara como bloqueada. Se investigó más a fondo en vez de dar el bloqueo
por definitivo: `dgcp.gob.do` (archivos estáticos) sigue bloqueado por
Cloudflare para `curl`, pero `datosabiertos.dgcp.gob.do` es un dominio y
producto distintos ("API DGCP") con REST completo, OCDS nativo incluido,
documentado con OpenAPI, licencia Apache 2.0 — verificado en vivo
(`totalResults=710144`, contrato más reciente de ayer). Estaba detrás de
Cloudflare también, pero en modo básico: bloqueaba el User-Agent por defecto
de `urllib`/`requests` específicamente, y pasaba limpio con un User-Agent de
navegador real. Esto también motivó reprobar Chile con la misma técnica por
las dudas — Chile siguió fallando 100% incluso con un User-Agent de
navegador real, confirmando que su problema es distinto (throttling por
frecuencia de conexión, no un filtro de User-Agent) y que el diagnóstico
anterior seguía siendo correcto.

Añadido `backend/scripts/ingest_dominican_republic_live.py`: 2,000
contratos, 0 fallidos, idempotente (verificado corriendo el script dos
veces). País agregado a los selectores del frontend, verificado en
navegador. Actualizados `PROGRESS.md` y `docs/architecture/fase2-relevamiento-paises.md`
para mover Rep. Dominicana de "bloqueada" a "integrada".

## 2026-08-15 — Costa Rica en vivo; Panamá y República Dominicana investigados y descartados por ahora

A pedido explícito del usuario: Panamá, Costa Rica, y República Dominicana.

- **Costa Rica: integrado.** SICOP no tiene API/OCDS (confirmado). El
  Observatorio de Compra Pública publica en cambio un ZIP mensual de CSVs de
  SICOP, actualizado a diario, en una URL documentada y predecible —
  verificado en vivo (`Last-Modified` del día anterior) antes de escribir
  código. `backend/scripts/ingest_costa_rica_live.py`: 1,643 contratos, 0
  fallidos, verificado en navegador. Trae un monto ya convertido a USD por el
  propio SICOP, sin necesidad de inventar una tasa de cambio como en
  Colombia. País agregado al selector del frontend.
- **Panamá: investigado a fondo, conector NO construido.** No estaba en el
  relevamiento original. Se encontró una API OCDS real, bien documentada
  (`ocds.panamacompraencifras.gob.pa`, tras descartar dos subdominios señuelo
  de desarrollo/versión anterior). Pero inspeccionando el contenido real de
  varios releases (2023 y 2024, no una sola muestra), `compiledRelease` nunca
  trae tender/award/value/description/proveedor — solo comprador y fecha. No
  es un problema de acceso, la API responde perfecto; es que el pipeline de
  publicación de Panamá no llena los campos sustantivos. Sumado a que no hay
  datos después de agosto 2024, se decidió no construir un conector que
  importaría contratos vacíos de contenido útil.
- **República Dominicana: bloqueada por Cloudflare, no por falta de API.**
  El portal CKAN oficial (`datos.gob.do`) funciona bien vía `curl` para
  metadata — confirmado contra los 6 datasets de la DGCP. Pero ninguno está
  en el datastore consultable de CKAN; todos son archivos estáticos en
  `dgcp.gob.do`, protegido por Cloudflare anti-bot (403 inmediato a `curl`,
  funciona en navegador real, verificado). No se intentó eludir la
  protección — es una decisión de anti-abuso deliberada del lado de DGCP.
- Los tres hallazgos quedan documentados con el mismo nivel de detalle que
  Chile en `PROGRESS.md` y `docs/architecture/fase2-relevamiento-paises.md` —
  ninguno se reporta como "no probado", cada uno tiene una causa raíz
  identificada.

## 2026-08-15 — Chile: conector escrito, bloqueado por throttling del servidor

- Se verificó en vivo la API OCDS pública de ChileCompra
  (`api.mercadopublico.cl/APISOCDS`, sin ticket, licencia CC0) y se escribió
  `backend/scripts/ingest_chile_live.py` siguiendo el mismo patrón que
  Colombia (idempotente vía `ocid`, sin conversión a USD, sin predicción del
  modelo NLP).
- El primer intento con poca pausa entre pedidos falló casi al 100%
  (conexiones cortadas por el servidor). En vez de asumir "hay que esperar
  más" sin evidencia, se investigó a fondo: se probó Python `urllib` con
  reintentos, `requests` con `HTTPAdapter`/`Retry` + `Connection: close`, y
  como descarte final, reemplazar todo el cliente HTTP por `curl` vía
  subprocess. **Los tres fallaron igual** en loop (incluso con 1.5–3s de
  pausa), lo que descarta un problema del stack HTTP de Python específico —
  es throttling real del servidor por frecuencia de conexión, con un umbral
  no documentado.
- Se decidió NO seguir ajustando el delay por prueba y error contra un
  servicio público de otro país — quedó registrado como bloqueado en
  `PROGRESS.md`, con las opciones concretas (contactar a ChileCompra por el
  umbral real, o aceptar un ritmo mucho más lento). El código queda listo
  para retomar apenas se resuelva esto, no hace falta reescribirlo.

## 2026-08-15 — Primera ingesta en vivo real: Colombia vía datos.gov.co

- El endpoint OCDS "oficial" de Colombia Compra Eficiente seguía sin poder
  verificarse (ver entrada anterior). Se buscó una alternativa y se encontró
  y verificó en vivo: **datos.gov.co** (portal oficial de datos abiertos del
  gobierno de Colombia) publica "SECOP II - Contratos Electrónicos"
  (`jbjy-vk9h`) sobre una API pública Socrata/SODA sin token, actualizada el
  mismo día que se escribió esto (~5.95M contratos totales).
- Añadido `backend/scripts/ingest_colombia_live.py`: ingesta en vivo real
  (no carga en bloque de un dataset ajustado por terceros) de los 5,000
  contratos más recientes, paginado, idempotente vía `id_contrato` (probado
  corriendo el script dos veces seguidas: la segunda vez, 0 nuevos, 5,000
  duplicados detectados correctamente). Trae fecha real de firma, a
  diferencia del dataset de terceros usado antes.
- Estos contratos no tienen predicción del modelo NLP ni score de anomalía
  (no hay pesos de BERT/XGBoost para inferencia en vivo en este entorno) —
  documentado como limitación real, no simulado.
- Colombia pasa de 1,548 a 6,548 contratos totales. Verificado en navegador:
  el contrato más reciente en el sistema tiene fecha 2026-08-14.
- Actualizado `docs/architecture/fase2-relevamiento-paises.md`: ya no hace
  falta perseguir el endpoint OCDS no verificado de Colombia Compra
  Eficiente, datos.gov.co es una fuente en vivo confirmada y en uso.
- Frontend: nota actualizada explicando las dos fuentes de Colombia (en vivo
  sin anomalía vs. dataset de terceros con anomalía pero sin fecha).

## 2026-08-15 — Colombia agregada como segundo país (dataset de terceros)

- A pedido explícito del usuario, se sacaron los datos de Colombia de
  https://contfrontdon.streamlit.app/ (app dormida de Streamlit Cloud del
  mismo autor del prototipo original). Su contenido real vive en un iframe
  interno; ahí estaba el link a
  [github.com/Daniel-Duque/cont_front_don](https://github.com/Daniel-Duque/cont_front_don)
  con el dataset completo ya procesado.
- Añadido `backend/scripts/migrate_colombia.py`: descarga los 40 CSV de ese
  repo (`data/cleaned0.csv`...`cleaned39.csv`, 1,548 filas en total) y los
  migra al mismo esquema que Paraguay. 1,548 contratos, 0 fallidos, 107
  marcados como anomalía.
- Extendido `predictions.predicted_value_original` en el esquema (backend/app/models.py,
  schemas.py) para poder guardar el valor predicho en la moneda original
  cuando no hay una conversión a USD verificable — es el caso de Colombia,
  cuyo dataset no trae fecha por contrato y por lo tanto no permite elegir una
  tasa de cambio histórica correcta. `amount_usd` y `predicted_value_usd`
  quedan NULL para Colombia por esa misma razón, documentado en el script, no
  fabricados.
- Frontend: selector de país en `/` y `/anomalies`, fallback de monto a
  "original + moneda" cuando no hay USD, link a la fuente original en SECOP
  en el detalle de contrato (Colombia sí trae `URLProceso` por fila).
  Verificado en navegador para ambos países (Paraguay y Colombia).
- Nota para el futuro, no resuelta ahora: el mismo repo de Colombia tiene
  `data/particular/`, datos crudos por municipio con fecha de firma real, pero
  sin clave de unión confiable hacia los CSVs ya procesados — path posible
  para completar `award_date` de Colombia más adelante.

## 2026-08-15 — Relevamiento de países para Fase 2

- Añadido `docs/architecture/fase2-relevamiento-paises.md`: de los 8 países
  pendientes de revisar (más allá de Paraguay ya integrado), Colombia, Chile,
  Perú y Ecuador tienen API OCDS documentada; Argentina, R. Dominicana,
  Honduras y Costa Rica solo ofrecen descarga en bloque (candidatos a Fase 4,
  no Fase 2); Nicaragua no tiene fuente OCDS conocida. Basado en búsqueda web,
  no en verificación directa de cada endpoint — eso queda como parte de
  implementar cada conector.
- Resuelto el bloqueo correspondiente en `PROGRESS.md`.

## 2026-08-15 — Fase 1: backend + frontend mínimo sobre el dataset existente

- Inicializado el repositorio git (no existía) con un commit inicial del
  prototipo tal cual estaba + los entregables de Fase 0.
- Añadido `backend/` (FastAPI + SQLAlchemy 2.0): modelos del esquema de Fase 1
  (`app/models.py`), API de solo lectura `/countries`, `/contracts`,
  `/contracts/{id}`, `/anomalies` (`app/main.py`), y script de migración
  (`scripts/migrate_dataset.py`) que carga `Data/resultados finales/resultados.xlsx`
  a la base de datos. Probado end-to-end contra SQLite local: 5,282 contratos
  migrados, 0 fallidos.
- Corregidos dos hallazgos durante la migración (documentados en el docstring
  del script y en `PROGRESS.md`):
  1. El dataset de resultados tiene 5,282 filas, no 3.55M como se mencionó en el
     pedido original — esa cifra probablemente corresponde al corpus crudo de
     entrenamiento (`Data/records.csv` + `Data/zips/`), no al archivo de
     resultados ya procesado. Falta confirmar con el equipo original.
  2. La columna `value_million_dolar` del archivo fuente está mal nombrada: el
     valor real está en miles de USD ajustados por CPI, no en millones
     (verificado numéricamente contra `Code/pre_procesamiento.ipynb`). El script
     de migración corrige la escala al cargar los datos.
- Añadido `frontend/` (Next.js + TypeScript, App Router): listado/búsqueda de
  contratos, explorador de anomalías, vista de detalle por contrato — todo
  consumiendo la API del backend, sin datos hardcodeados.
- Añadido `docker-compose.yml` con Postgres para cuando haya Docker disponible
  (no lo había en este entorno de desarrollo — ver `PROGRESS.md`); el esquema de
  `backend/app/models.py` es agnóstico del motor (SQLite en dev, Postgres en
  producción vía `DATABASE_URL`).
- Verificado el frontend en navegador contra el backend real (no solo `curl` a
  la API) y encontrado ahí un bug que la prueba de API sola no mostraba: la
  migración marcaba el 100% de los contratos como "anomalía" porque no aplicaba
  ningún corte a `perc_error`. Corregido con un umbral provisional y documentado
  (`ABS_PERC_ERROR_THRESHOLD = 1.0` en `migrate_dataset.py`) — de 5,282 pasó a
  696 contratos marcados. Ver `PROGRESS.md` para el detalle.

## 2026-08-14 — Fase 0: Planificación de la plataforma pública

- Añadido `docs/architecture/PLANNING.md`: diagrama de arquitectura (mermaid),
  stack técnico recomendado, modelo de datos, roadmap por fases (1-6), riesgos y
  mitigaciones, estrategia de validación de precisión, y plan de despliegue.
- Añadidos `docs/adr/0001` (plataforma pública multi-país en vez de extender el
  Streamlit interno), `0002` (LiteLLM sobre OpenRouter para enrutamiento de LLM),
  `0003` (modelo estadístico interno independiente como validación cruzada del
  NLP/LLM).
- Añadido `PROGRESS.md` como estado vivo del desarrollo, con bloqueos registrados
  (clave OpenRouter, credenciales de object storage, alcance de países para Fase 2,
  inicialización de git) y el siguiente paso concreto (Fase 1: migrar el dataset
  existente de 3.55M contratos a Postgres + API de solo lectura).
- No se modificó código del prototipo existente (`main.py`, notebooks en `Code/`,
  `Models/modelxgboost.pkl`) — esta iteración fue puramente de planificación.
