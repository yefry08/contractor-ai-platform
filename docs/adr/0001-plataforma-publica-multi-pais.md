# ADR 0001 — De prototipo Streamlit interno a plataforma pública multi-país

## Estado
Aceptado (2026-08-14)

## Contexto
El prototipo actual (`main.py`) es una app Streamlit de un solo archivo que lee un
Excel pre-calculado (`Data/resultados finales/resultados.xlsx`, 3.55M+ contratos de
Paraguay, con exploración inicial de Colombia en `Code/main_colombia.ipynb`). Sirve
como herramienta interna de análisis, no como producto público: no tiene API, no
soporta ingesta en vivo, no acepta carga de contratos por parte de terceros, y está
acoplado a un único formato/país de entrada.

El objetivo declarado es evolucionar esto a una plataforma pública, multi-país
(países OCDS/PIDA de Latinoamérica), con API abierta y carga multimodal
(PDF/link/foto) para cualquier usuario.

## Decisión
Separar el sistema en capas independientes — ingesta, normalización, análisis
(NLP + estadístico), almacenamiento, API, frontend — en vez de extender el script
Streamlit. El Streamlit actual se conserva como herramienta interna de analista, no
se elimina, pero deja de ser el producto de cara al público.

La normalización usa el esquema OCDS como formato canónico interno, dado que ya es
el estándar de origen de la mayoría de las fuentes objetivo y el que ya maneja el
prototipo (columnas `compiledRelease/...` en los datos actuales).

## Consecuencias
- Se requiere una migración explícita del dataset ya validado (3.55M contratos) a
  Postgres como parte de la Fase 1, en vez de descartarlo.
- Cualquier país nuevo se agrega como una fila en `countries` + un conector, sin
  tocar el núcleo de análisis — el modelo NLP y el estadístico son agnósticos de país
  salvo por el `reference_group` usado en el cálculo de outliers.
- El Streamlit interno puede quedar desactualizado si no se mantiene deliberadamente;
  se acepta ese costo porque no es la prioridad del roadmap público.
