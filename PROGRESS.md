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

## Bloqueado — pendiente de credencial/decisión humana

- **Clave de API de OpenRouter** (o proveedor LLM equivalente) — necesaria para
  cualquier tarea de extracción/resumen vía LLM (ADR 0002). No simular respuestas
  de LLM sin esta clave.
- **Credenciales de object storage de producción** (S3/MinIO) — necesarias antes de
  poder desplegar el flujo de carga multimodal (Fase 3) fuera de dev local.
- **Confirmación de alcance de países para Fase 2** — más allá de Paraguay y
  Colombia (ya presentes en el prototipo), falta relevar qué otros países del
  listado (R. Dominicana, Argentina, Perú, Chile, Ecuador, Honduras, Costa Rica,
  Nicaragua) tienen API OCDS suficientemente limpia vs. requieren scraper (Fase 4).
  Esto es una decisión de alcance, no una credencial, pero bloquea planificar el
  detalle de Fase 2 conector por conector.
- **Repositorio git**: el directorio de trabajo actual no es un repositorio git
  (`git status` no aplica). Se recomienda `git init` + primer commit antes de
  empezar Fase 1, para que el historial de cambios sea auditable como pide el modo
  de operación en loop. No se ha hecho todavía — requiere confirmación porque es
  una decisión de estructura del proyecto, no solo de código.

## Siguiente paso concreto

Iniciar **Fase 1**: migrar `Data/resultados finales/resultados.xlsx` (3.55M
contratos) a un esquema Postgres siguiendo el modelo de datos de
`docs/architecture/PLANNING.md` §3, y exponer un servicio FastAPI de solo lectura
(`/contracts`, `/contracts/{id}`, `/anomalies`) sobre esos datos ya existentes —
sin ingesta en vivo todavía. No depende de ninguno de los bloqueos de arriba.

## Notas de operación

- El único gate humano explícito del flujo autónomo es el **despliegue a
  producción** (ver §7 del plan) — el resto de las fases puede avanzar sin
  aprobación paso a paso.
- No inventar ni simular credenciales, datos de países no verificados, ni
  resultados de modelos. Si falta algo, se registra arriba y se continúa con la
  siguiente tarea no bloqueada.
