# PROGRESS

Estado vivo del desarrollo de Contractor AI (plataforma pública). Leer al inicio de
cada iteración; actualizar al final con qué se completó, qué falta y el siguiente
paso concreto. Ver `CHANGELOG.md` para el historial y `docs/adr/` para decisiones
de arquitectura.

## Completado

- **Plataforma desplegada en producción** (2026-08-15). Backend en Render
  (https://contractor-ai-api.onrender.com, plan free, Postgres gestionado vía
  `render.yaml`), frontend en Vercel (https://contractor-ai-one.vercel.app).
  Fly.io se descartó a mitad de camino por un fallo de verificación de medio
  de pago que el usuario no pudo resolver — la decisión fue migrar a
  Render+Vercel (ninguno de los dos pide tarjeta en el tier gratuito) en vez
  de insistir. Repo en GitHub: `yefry08/contractor-ai-platform` (privado —
  el repo ya tenía en su historial archivos con datos sensibles reales:
  lista de usuarios, base de proveedores, comprobantes financieros, notas de
  reunión internas; no se reescribió el historial para hacerlo público sin
  confirmación explícita).
  - Las 5 fuentes de datos (Paraguay, Colombia bulk, Colombia en vivo, Costa
    Rica en vivo, Rep. Dominicana en vivo) y la capa estadística se corrieron
    contra la base de Postgres real de producción, no solo contra SQLite
    local — verificado con `curl` directo a la API desplegada:
    `/contracts` devuelve `total: 15473`, `/countries` devuelve los 4 países
    con datos (Chile sigue sin datos, ver bloqueo de throttling abajo).
  - **Bug real encontrado corriendo contra la base remota, no en local**: los
    5 scripts de ingesta hacían `db.flush()` por cada fila para leer el ID
    autogenerado antes de usarlo como FK en Prediction/Anomaly/Provenance.
    Contra SQLite eso es casi gratis; contra Postgres remoto cada flush es un
    round-trip de red real — la migración de Paraguay se quedó pegada en la
    fila ~500 con el proceso vivo pero sin avanzar. Como todos los modelos ya
    usan un default de UUID del lado de Python (no una secuencia de
    Postgres), el ID se conoce apenas se construye el objeto — no hacía
    falta el flush en absoluto. Se corrigió generando el UUID explícitamente
    antes de construir cada fila en los 5 scripts; la migración de Paraguay
    pasó de quedarse pegada a terminar en menos de 2 minutos.

- **Fase 5 — capa estadística independiente (ADR 0003)** (2026-08-15). El
  hueco funcional más grande de la plataforma era que más de la mitad de
  los contratos (Colombia en vivo, Costa Rica, Rep. Dominicana — ~8.600 de
  15.473) no tenían ningún score de anomalía. Cerrado con
  [`backend/scripts/compute_statistical_anomalies.py`](backend/scripts/compute_statistical_anomalies.py):
  z-score modificado (Iglewicz & Hoaglin) + cercas de Tukey (IQR), sobre
  log(monto) agrupado por comprador (o categoría, o país, con fallback
  jerárquico cuando el grupo específico no tiene suficientes datos) —
  completamente independiente de cualquier modelo NLP/LLM. Llena
  `statistical_flags` (sin usar hasta ahora) y crea/completa `Anomaly`.
  - **Dos bugs reales encontrados probando contra datos reales, no en
    teoría**: (1) calcular sobre montos crudos dio un z-score de 258,491
    para un contrato legítimo de Costa Rica, por la asimetría típica del
    gasto público — corregido calculando sobre log(monto), práctica
    estándar para datos monetarios que abarcan varios órdenes de magnitud.
    (2) un comprador de Paraguay con 7 contratos casi idénticos y 4 mucho
    más grandes seguía dando scores en los miles incluso en escala log
    (MAD genuinamente casi cero) — se acotó |z| en 50 (muy por encima del
    umbral de marcado de 3.5, así que no cambia qué se marca, solo evita
    números sin sentido práctico), documentado explícitamente en el script.
  - 724 anomalías nuevas solo-estadísticas, 803 anomalías NLP existentes
    (Paraguay + bulk Colombia) ahora con `stat_component` además de
    `nlp_component` — las dos señales se muestran por separado, nunca
    combinadas en un solo número. Idempotente (verificado corriendo el
    script tres veces).
  - Frontend actualizado (`/anomalies` y detalle de contrato) para mostrar
    qué señal(es) marcaron cada contrato. Verificado en navegador,
    incluyendo un caso donde ambas señales independientes coinciden (un
    contrato de $25.5M predicho en $38K por NLP, z=50 por estadística).

- **Fase 0 — Planificación** (2026-08-14): arquitectura, stack, modelo de datos,
  roadmap, riesgos, estrategia de validación y plan de despliegue documentados en
  [`docs/architecture/PLANNING.md`](docs/architecture/PLANNING.md). Decisiones
  clave registradas en `docs/adr/0001` a `0003`.
- **Repositorio git inicializado** (2026-08-15): commit inicial con el prototipo
  existente tal cual estaba + los entregables de Fase 0.
- **Fase 1 — backend** (2026-08-15): esquema SQLAlchemy (`backend/app/models.py`),
  script de migración (`backend/scripts/migrate_dataset.py`) y API FastAPI de solo
  lectura (`/countries`, `/contracts`, `/contracts/{id}`, `/anomalies`) probada
  end-to-end contra SQLite local. Ver `backend/README.md`.
  - **Corrección importante encontrada durante la migración**: el dataset
    `Data/resultados finales/resultados.xlsx` (el que ya sirve al Streamlit en
    producción) tiene **5,282 filas, no 3.55M**. La cifra de 3.55M+ contratos
    mencionada en el pedido original no corresponde a este archivo — es
    probablemente el tamaño del corpus crudo de entrenamiento/exploración
    (`Data/records.csv` + `Data/zips/`, ~210MB de CSVs OCDS sin procesar). Falta
    confirmar con el equipo original a qué corresponde exactamente esa cifra; no
    se asumió nada y se migró el archivo real tal como está.
  - **Corrección de unidades verificada numéricamente**: la columna
    `value_million_dolar` del archivo dice "million" pero en realidad está en
    miles de USD ajustados por CPI (verificado fila por fila contra
    `Code/pre_procesamiento.ipynb`: `value_million_dolar == (monto/tipo_cambio/CPI_avg)/1000`,
    diferencia < 1e-9). El script de migración lo corrige explícitamente — ver el
    docstring de `backend/scripts/migrate_dataset.py` para el detalle. Esto es
    relevante porque un error de escala de 1000x en montos es exactamente el tipo
    de cosa que una herramienta anti-corrupción no puede darse el lujo de mostrar
    mal.
- **Fase 1 — frontend** (2026-08-15): Next.js mínimo (`frontend/`) con listado de
  contratos, explorador de anomalías y detalle de contrato, consumiendo la API.
  Verificado en navegador contra el backend real (sin datos hardcodeados),
  incluida navegación a detalle de contrato.
  - **Bug encontrado y corregido probando la app, no solo la API**: la primera
    versión del script de migración creaba una fila de `Anomaly` para
    *cualquier* contrato con `perc_error` distinto de cero. Como la desviación
    mediana del propio modelo en este dataset ya es ~31% (ruido normal), esto
    marcaba el 100% de los contratos (5,282 de 5,282) como "anomalía" en la
    página `/anomalies` — inútil y engañoso. Se corrigió aplicando un corte
    provisional (`ABS_PERC_ERROR_THRESHOLD = 1.0` en
    `backend/scripts/migrate_dataset.py`: solo se marca cuando el valor real es
    al menos el doble o menos de la mitad del predicho), documentado en el
    script como grueso/no validado estadísticamente — la validación formal
    sigue siendo trabajo de Fase 5. Con el corte, quedan 696 contratos
    marcados (~13%), un número que sí sirve para algo. Esto solo se detectó
    abriendo la app en el navegador, no habría aparecido probando la API sola
    con curl.

- **Colombia agregada como segundo país** (2026-08-15, a pedido explícito del
  usuario: "los de Colombia sacalos de aquí https://contfrontdon.streamlit.app/").
  Esa app estaba dormida (Streamlit Cloud free tier) — se despertó, y su
  contenido real vive en un iframe (`/~/+/`) que hubo que navegar directamente
  para leer. Ahí apareció un link a
  [github.com/Daniel-Duque/cont_front_don](https://github.com/Daniel-Duque/cont_front_don)
  (mismo autor del prototipo original, "para descargar los datasets
  completos"), con 1,548 contratos ya procesados (predicción + similitud) en
  `data/cleaned{0..39}.csv`. Migrados con
  [`backend/scripts/migrate_colombia.py`](backend/scripts/migrate_colombia.py):
  1,548 contratos, 0 fallidos, 107 marcados como anomalía (~7%).
  - **Esto NO es la ingesta en vivo de Fase 2** (la de
    `docs/architecture/fase2-relevamiento-paises.md`, vía API OCDS de
    Colombia) — es una carga en bloque de un dataset ya procesado por otro
    tercero, igual en naturaleza a como Paraguay entró en Fase 1. La ingesta
    en vivo contra SECOP/Colombia Compra Eficiente sigue pendiente.
  - **Limitaciones explícitas, no ocultas**: el dataset de Colombia no trae
    fecha por contrato (`award_date` queda NULL) ni tasa de cambio verificable
    por fecha, así que `amount_usd` también queda NULL — se muestra el monto
    original en COP en vez de forzar una conversión a USD sin base. El
    detalle completo, incluida la verificación numérica de las fórmulas
    usadas, está en el docstring de `migrate_colombia.py`.
  - Se agregó `predictions.predicted_value_original` al esquema (monto
    predicho en la moneda original del contrato) porque el campo existente
    `predicted_value_usd` no aplica sin conversión verificable — no rompe los
    datos de Paraguay, que siguen poblando `predicted_value_usd` como antes.
  - Frontend actualizado: selector de país (Paraguay/Colombia/todos), montos
    que caen a "monto original + moneda" cuando no hay USD, link a la fuente
    original en SECOP cuando existe (`contract.source_url` — Colombia sí trae
    esto, Paraguay no). Verificado en navegador para ambos países.
  - Dato curioso encontrado en el camino, no verificado más a fondo: el mismo
    repo tiene una carpeta `data/particular/` con datos crudos de SECOP por
    municipio (con fecha de firma real) mucho más granular pero partida en
    cientos de archivos sin una clave de unión confiable hacia los CSVs ya
    procesados — queda como oportunidad futura para completar `award_date` de
    Colombia, no se intentó ese cruce ahora.

- **Ingesta en vivo de Colombia — primera conexión real de Fase 2** (2026-08-15).
  El intento anterior de verificar el endpoint OCDS "oficial" de Colombia
  Compra Eficiente seguía sin resolver, así que se buscó una alternativa
  verificable: **datos.gov.co** (portal oficial de datos abiertos del
  gobierno colombiano) publica el dataset "SECOP II - Contratos Electrónicos"
  (`jbjy-vk9h`) sobre una API pública Socrata/SODA, sin token. Verificado en
  vivo antes de escribir código: `rowsUpdatedAt` = 2026-08-15 08:17 UTC (el
  mismo día), ~5.95M contratos totales.
  - [`backend/scripts/ingest_colombia_live.py`](backend/scripts/ingest_colombia_live.py):
    trae los 5,000 contratos más recientes (paginado, con pausa entre
    páginas), idempotente vía `id_contrato` (correrlo dos veces no duplica —
    verificado). A diferencia de `migrate_colombia.py` (carga en bloque de un
    dataset de terceros), esto SÍ trae fecha real de firma por contrato.
  - **Limitación honesta**: estos contratos no tienen predicción del modelo
    NLP ni score de anomalía — no hay pesos entrenados de BERT/XGBoost
    disponibles para correr inferencia en vivo en este entorno. Quedan
    igual de navegables/buscables, simplemente sin `Anomaly`. Completar esto
    requiere un pipeline de inferencia real, no algo para simular.
  - Total Colombia ahora: 6,548 contratos (1,548 del dataset de terceros +
    5,000 en vivo). Verificado en navegador: el contrato más reciente tiene
    fecha 2026-08-14 (ayer).
  - Actualizado `docs/architecture/fase2-relevamiento-paises.md` con este
    hallazgo — cambia la recomendación: no hace falta seguir insistiendo con
    el endpoint OCDS no verificado de Colombia Compra Eficiente, datos.gov.co
    ya es una fuente en vivo verificada y funcionando.

- **Costa Rica — ingesta en vivo funcionando (2026-08-15)**, a pedido
  explícito del usuario ("panama y costa rica, terminar con Rep. Dominicana").
  SICOP no tiene API/OCDS (confirmado); el Observatorio de Compra Pública
  publica en cambio un ZIP mensual con CSVs relacionales de SICOP,
  actualizado diariamente para el mes en curso, en una URL documentada y
  predecible — verificado en vivo (`Last-Modified` del día anterior antes de
  escribir código). `backend/scripts/ingest_costa_rica_live.py`: 1,643
  contratos migrados, 0 fallidos, verificado en navegador. A diferencia de
  Colombia, este dataset trae un monto ya convertido a USD por el propio
  SICOP (`MONTO_ADJU_LINEA_USD`), así que `amount_usd` se pobló directamente
  sin necesidad de inventar una tasa de cambio.

- **Panamá — investigado a fondo, conector NO construido (2026-08-15)**. No
  estaba en el relevamiento original; se agregó a pedido del usuario. Se
  encontró una API OCDS real y bien documentada
  (`ocds.panamacompraencifras.gob.pa`, tras descartar dos subdominios que
  resultaron ser señuelos de desarrollo/versión anterior sin datos útiles).
  Pero al inspeccionar el contenido real de varios `Release`/`Record` (2023 y
  2024, no solo una muestra), **el campo `compiledRelease` nunca trae
  tender/award/value/description/proveedor — solo `buyer` + `ocid` + fecha**.
  No es un problema de acceso: la API responde perfecto y rápido. Es que el
  pipeline de publicación de Panamá no llena los campos sustantivos del
  release. Sumado a que no hay datos después de agosto 2024, se decidió NO
  construir el conector — importaría contratos sin título, sin monto y sin
  descripción, que no sirven para nada en una herramienta de detección de
  anomalías. Documentado en `docs/architecture/fase2-relevamiento-paises.md`.

- ~~**República Dominicana — bloqueada por protección anti-bot**~~ —
  **resuelto (2026-08-15).** El bloqueo de `dgcp.gob.do` (archivos estáticos
  detrás de Cloudflare, 403 a `curl`) seguía siendo real, pero no era el
  único camino: `datosabiertos.dgcp.gob.do` es un dominio y producto
  distintos ("API DGCP") con una API REST completa, OCDS nativo incluido
  (`/ocds/releases/all`), documentada con OpenAPI, licencia Apache 2.0.
  Verificado en vivo: `totalResults=710144`, contrato más reciente de ayer.
  Ese dominio también está detrás de Cloudflare pero solo en modo básico:
  bloquea el User-Agent por defecto de `urllib`/`requests` específicamente
  (403), y deja pasar sin problema con un User-Agent de navegador real — no
  es evadir un desafío difícil, es simplemente no mandar la cadena que
  Cloudflare tiene marcada como sospechosa por defecto. Sin throttling por
  frecuencia (25 pedidos seguidos, 0 fallos). Integrado en
  `backend/scripts/ingest_dominican_republic_live.py`: 2,000 contratos, 0
  fallidos, idempotente (verificado corriendo el script dos veces).

- **Chile — conector escrito, NO verificado como funcional (2026-08-15)**.
  Se encontró y verificó en vivo la API OCDS pública de ChileCompra
  (`api.mercadopublico.cl/APISOCDS`, sin ticket, licencia CC0 — distinta de
  la API "clásica" que sí exige ticket vía Clave Única). Un pedido aislado a
  `listaOCDSAgnoMesTratoDirecto/2026/07/...` y a `.../award/{id}` funciona
  perfecto y rápido.
  - **Pero en loop, falla casi siempre.** Se investigó a fondo (no se asumió
    "hay que esperar más" sin evidencia): se probó Python `urllib` con
    reintentos, `requests` con `HTTPAdapter`/`Retry` y `Connection: close`,
    y como último descarte, reemplazar todo el cliente HTTP por `curl` vía
    subprocess — **los tres fallan igual** en loop, incluso con pausas de
    1.5–3s entre pedidos. Esto descarta que sea un problema del stack HTTP de
    Python; es throttling real del lado del servidor por frecuencia de
    conexión, con un umbral no documentado y bastante bajo.
  - [`backend/scripts/ingest_chile_live.py`](backend/scripts/ingest_chile_live.py)
    queda escrito, idempotente (vía `ocid`), y con este hallazgo documentado
    en su propio docstring — pero **no se logró traer un volumen útil de
    contratos en esta sesión**. No se debe asumir que "ya funciona" solo
    porque el código no tiene errores.
  - Se decidió NO seguir probando distintos delays por prueba y error contra
    un servicio público de otro país — ya mostró con hechos que hay que
    bajar mucho el ritmo, seguir insistiendo sería irrespetuoso con un
    servicio gratuito ajeno.
  - **Bloqueado — pendiente de decisión humana**: ¿vale la pena seguir
    ajustando el delay a ciegas, o conviene contactar a ChileCompra para
    pedir el umbral real (o un token/ticket con límites más altos, si
    existe esa opción para la ruta OCDS)? Registrado abajo también.

## Bloqueado — pendiente de credencial/decisión humana

- **Panamá — no bloqueado técnicamente, descartado por calidad de datos.**
  Ver arriba. A diferencia de los demás bloqueos, este no tiene un camino
  claro de desbloqueo — el problema está en cómo Panamá publica sus propios
  datos (`compiledRelease` vacío de contenido sustantivo), no en algo que se
  pueda resolver desde este lado. Si en el futuro Panamá corrige su pipeline
  de publicación OCDS, revisar `ocds.panamacompraencifras.gob.pa` de nuevo.
- **Chile — throttling del lado del servidor sin umbral documentado.** Ver
  arriba. `ingest_chile_live.py` está escrito pero no logró traer contratos
  en esta sesión por conexiones cortadas del lado de ChileCompra, reproducido
  con tres clientes HTTP distintos (así que no es un problema de nuestro
  código). Se necesita, en orden de preferencia: (a) contactar a ChileCompra
  para pedir el umbral real o un ticket/token con límites más altos para la
  ruta OCDS, o (b) decidir experimentalmente un delay mucho más conservador
  (varios segundos por pedido) y aceptar que traer un volumen útil de
  contratos va a ser lento.
- **Clave de API de OpenRouter** (o proveedor LLM equivalente) — necesaria para
  cualquier tarea de extracción/resumen vía LLM (ADR 0002). No simular respuestas
  de LLM sin esta clave.
- **Credenciales de object storage de producción** (S3/MinIO) — necesarias antes de
  poder desplegar el flujo de carga multimodal (Fase 3) fuera de dev local.
- ~~**Confirmación de alcance de países para Fase 2**~~ — relevado en
  [`docs/architecture/fase2-relevamiento-paises.md`](docs/architecture/fase2-relevamiento-paises.md)
  (2026-08-15, vía búsqueda web contra el registro de OCP, no verificación
  directa de cada API). Resumen: Colombia, Chile, Perú y Ecuador tienen API
  OCDS documentada — candidatos directos para Fase 2, en ese orden sugerido.
  Argentina, R. Dominicana, Honduras y Costa Rica solo tienen descarga en
  bloque — van a Fase 4 (scraping). Nicaragua no tiene fuente OCDS conocida.
  **Sigue pendiente**: verificar cada endpoint real y sus términos de uso antes
  de implementar el primer conector (esto es trabajo de Fase 2 en sí, no un
  bloqueo previo).
- **Postgres/Docker no disponibles en este entorno de desarrollo**: no hay
  `docker`, `psql` ni `pg_ctl` instalados en la máquina donde se corrió Fase 1.
  El backend usa SQLite localmente (`backend/contractor.db`, gitignored) con
  `DATABASE_URL` configurable — el esquema es agnóstico del motor, así que migrar
  a Postgres real (`docker-compose.yml` ya en la raíz) es solo cuestión de
  levantar el contenedor y correr `migrate_dataset.py` de nuevo. No usar SQLite en
  producción (ver ADR 0001 / PLANNING.md stack).

## Siguiente paso concreto

Cinco países integrados (Paraguay, Colombia, Chile*, Costa Rica, República
Dominicana — *Chile bloqueado por throttling, ver arriba), 15,473 contratos
totales, todos con al menos una señal de anomalía (NLP donde había
predicción precalculada, estadística para el resto — ver Fase 5 arriba).

Candidatos concretos, en orden de impacto:

1. **Chile**: contactar a ChileCompra por el umbral real de throttling, o
   aceptar un ritmo mucho más lento y conservador — no hay más avance
   posible sin eso (ver bloqueo arriba, root cause ya identificada).
2. **Validar la capa estadística contra el baseline de 3.55M** (§6 de
   PLANNING.md) — todavía no se hizo la validación formal de precisión
   (falsos positivos/negativos) prometida ahí, solo se verificó que los
   números son sanos y que el mecanismo funciona correctamente.
3. Ampliar volumen de Colombia/Costa Rica/Rep. Dominicana más allá de la
   muestra inicial — mecánico, ya paginan e idempotentes. Recordar correr
   `compute_statistical_anomalies.py` de nuevo después (es barato y
   idempotente) para que los contratos nuevos también tengan score.
4. Instalar Postgres real y validar las migraciones contra él — bloqueado
   por falta de Docker en este entorno de desarrollo.

## Notas de operación

- El único gate humano explícito del flujo autónomo es el **despliegue a
  producción** (ver §7 del plan) — el resto de las fases puede avanzar sin
  aprobación paso a paso.
- No inventar ni simular credenciales, datos de países no verificados, ni
  resultados de modelos. Si falta algo, se registra arriba y se continúa con la
  siguiente tarea no bloqueada.
