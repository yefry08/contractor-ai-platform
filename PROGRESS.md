# PROGRESS

Estado vivo del desarrollo de Contractor AI (plataforma pública). Leer al inicio de
cada iteración; actualizar al final con qué se completó, qué falta y el siguiente
paso concreto. Ver `CHANGELOG.md` para el historial y `docs/adr/` para decisiones
de arquitectura.

## Completado

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

## Bloqueado — pendiente de credencial/decisión humana

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

Fase 1 está funcionalmente completa y verificada en navegador (backend +
frontend + migración, ver arriba). El relevamiento de países para Fase 2 ya
está hecho (`docs/architecture/fase2-relevamiento-paises.md`), con Colombia
como primer candidato sugerido.

**Intento de verificar el endpoint real de Colombia (2026-08-15): sin
resolver.** La página oficial de Colombia Compra Eficiente
(operaciones.colombiacompra.gov.co/transparencia/estandar-ocds) confirma que
existe una API OCDS pero no publica la URL del endpoint, ni límites de tasa,
ni términos de uso específicos para acceso programático — y el pie de página
dice "© 2020", lo que no permite confirmar si sigue mantenida. No se debe
adivinar ni construir un conector contra una URL no verificada de un sistema
de gobierno real. Alternativa a evaluar antes de escribir código de Fase 2:
Colombia también publica en datos.gov.co sobre la plataforma Socrata (ej.
dataset "Contratos Secop II", resource id `tb27-zmix`), que sí tiene API
pública documentada (Socrata SODA API) aunque no sea nativamente OCDS —
requeriría mapeo de campos en vez de reutilizar el parser OCDS existente.

Próximo paso concreto: (a) contactar a Colombia Compra Eficiente para pedir la
documentación técnica del endpoint OCDS (datos de contacto en la página
oficial), o (b) evaluar directamente la API de datos.gov.co/Socrata como
alternativa más verificable, antes de escribir el primer conector de Fase 2.
Mientras tanto, sin bloquear lo anterior: instalar Postgres real (vía
`docker-compose.yml`) y validar que la migración corre igual contra él, ya que
todo lo probado hasta ahora fue sobre SQLite por falta de Docker en este
entorno.

## Notas de operación

- El único gate humano explícito del flujo autónomo es el **despliegue a
  producción** (ver §7 del plan) — el resto de las fases puede avanzar sin
  aprobación paso a paso.
- No inventar ni simular credenciales, datos de países no verificados, ni
  resultados de modelos. Si falta algo, se registra arriba y se continúa con la
  siguiente tarea no bloqueada.
