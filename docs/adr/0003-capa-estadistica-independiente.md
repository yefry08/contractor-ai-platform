# ADR 0003 — Modelo estadístico interno como validación cruzada independiente del NLP/LLM

## Estado
Aceptado (2026-08-14)

## Contexto
El sistema actual predice un valor de referencia usando un BERT multilenguaje
ajustado + XGBoost, y compara ese valor contra el valor real reportado
(`Valor real` vs `Valor Proyectado` en `main.py`) para estimar sobrecosto/subcosto.
Este enfoque depende enteramente de un modelo de lenguaje entrenado — si el modelo
tiene un sesgo sistemático (por ejemplo, subestima contratos de una categoría poco
representada en el entrenamiento), no hay nada que lo contraste.

El pedido original exige explícitamente una capa estadística/matemática interna,
no dependiente de terceros, como validación cruzada frente al NLP/LLM.

## Decisión
Implementar un motor de detección de outliers puramente estadístico
(`scipy`/`statsmodels`/`scikit-learn`: IQR, z-score, regresión robusta) que calcula
un score de anomalía **de forma completamente independiente** del modelo NLP y de
cualquier LLM, agrupando por categoría × entidad compradora × país
(`reference_group` en `statistical_flags`). El score final de anomalía (`anomalies.
composite_score`) es una fusión explícita de ambas señales (`nlp_component` +
`stat_component`), nunca un solo modelo por sí solo.

Los LLMs (vía OpenRouter/LiteLLM, ADR 0002) se usan únicamente para narrativa y
extracción, nunca para decidir si un contrato es anómalo.

## Consecuencias
- Cuando NLP y estadístico coinciden, la confianza del score es alta; cuando
  divergen, el contrato va a una cola de revisión curada (ver §6 de
  `docs/architecture/PLANNING.md`) en vez de resolverse automáticamente a favor de
  uno de los dos.
- El sistema estadístico funciona incluso en países sin suficiente historial para
  afinar el BERT — sirve de fallback razonable mientras no hay modelo NLP confiable
  para ese país (ver riesgo #7 en el plan).
- Requiere mantener y versionar el modelo estadístico igual que el modelo NLP
  (métricas de precisión propias, no solo las del NLP) — se prueban ambos contra el
  baseline congelado de 3.55M contratos antes de cualquier cambio de umbral.
