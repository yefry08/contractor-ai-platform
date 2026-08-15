# Changelog

Formato libre, orden cronológico inverso (más reciente arriba). Referencia a
`docs/adr/` para el razonamiento detrás de decisiones de arquitectura.

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
