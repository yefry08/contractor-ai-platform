# ADR 0002 — Enrutamiento de LLMs vía LiteLLM sobre OpenRouter

## Estado
Aceptado (2026-08-14)

## Contexto
La plataforma necesita LLMs para tareas de extracción, resumen y narrativa (no para
el score de anomalía en sí, ver ADR 0003), con distintos requisitos de costo/latencia/
calidad según la tarea: extraer texto estructurado de un PDF escaneado es distinto de
resumir por qué un contrato fue marcado como anómalo para un periodista. El pedido
original menciona OpenRouter como opción primaria y "omniroute" u otro agregador
equivalente a evaluar.

## Decisión
Usar **LiteLLM** (proxy open-source, self-hosteable) como capa de enrutamiento, con
OpenRouter configurado como uno de los proveedores detrás de él, no como el único
punto de entrada. Las reglas de selección de modelo por costo/latencia/calidad se
definen en código/config dentro de LiteLLM, con fallback a otro proveedor si uno falla
o está caro/lento en un momento dado.

Se descarta atarse únicamente a OpenRouter como agregador único porque introduce un
punto único de falla y de negociación de costo para un proyecto público que depende
de donaciones/presupuesto limitado. Se descarta "omniroute" u otros agregadores
propietarios equivalentes como dependencia principal hasta que se evalúen
concretamente contra LiteLLM (self-hosteable, sin costo de licencia, con comunidad
activa) — no bloquea Fase 0 ni Fase 1, se revisita en Fase 6 (enrutamiento LLM
formal).

## Consecuencias
- Cualquier proveedor LLM adicional (Anthropic, OpenAI, modelos locales) se agrega
  como config en LiteLLM sin tocar el código de la aplicación.
- Requiere mantener credenciales de al menos un proveedor real (OpenRouter u otro);
  hasta que exista esa credencial, las tareas que dependen de LLM quedan bloqueadas
  y registradas en `PROGRESS.md`, no simuladas.
- El LLM nunca es la única fuente de verdad de un score de anomalía (ver ADR 0003),
  así que un fallo o caída del proveedor LLM degrada narrativas/resúmenes, pero no
  invalida el sistema de detección.
