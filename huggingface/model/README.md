---
license: mit
language:
  - es
  - pt
  - en
tags:
  - public-procurement
  - anomaly-detection
  - open-contracting
  - ocds
  - latin-america
  - transparency
  - xgboost
pretty_name: Contractor AI — contratación pública en 10 países de LATAM
---

# Contractor AI · modelos para analizar contratos públicos

Dos piezas para revisar contratos públicos de América Latina **fuera de la plataforma**:

| Carpeta | Qué es | ¿Analiza un contrato nuevo por sí sola? |
|---|---|---|
| `analyzer.py` + `reference.json` | Modelo de referencia estadístico de 10 países (mediana + MAD sobre el logaritmo del monto). El mismo cálculo que usa la página «Analizar contratos» de [Contractor AI](https://contractor-ai-one.vercel.app/analyze). | **Sí.** Solo Python estándar, sin internet. |
| `bert-xgboost/` | El modelo base original de **Daniel Duque Lozano**: un XGBoost que predice el valor de un contrato a partir de la descripción (vía BERT) y de campos OCDS. Entrenado con contratos de servicios de Paraguay. | **No**, falta la red BERT ajustada (ver abajo). |

Países: Paraguay, Colombia, Costa Rica, República Dominicana, Perú, El Salvador, Brasil, Uruguay, Chile y Guatemala.

Pruébalo sin instalar nada en el analizador en línea: **[ElDoctor/contractor-ai-analizador](https://huggingface.co/spaces/ElDoctor/contractor-ai-analizador)**.

## Uso rápido

```bash
pip install huggingface_hub
python -c "from huggingface_hub import snapshot_download; print(snapshot_download('ElDoctor/contractor-ai-latam'))"
cd <carpeta que imprimió>
python analyzer.py --country GT --amount 89500
python analyzer.py --country PY --amount 950000000 --buyer "municipalidad de asuncion"
python analyzer.py --list CL      # categorías y compradores disponibles
```

```python
from analyzer import Analyzer
r = Analyzer().compare("DO", 265000)          # moneda principal del país por defecto
print(r.verdict, r.reference_group, round(r.deviation_pct))
```

### Cómo decide

1. Elige el grupo de referencia más específico con al menos 8 contratos: **mismo comprador**, si no **misma categoría**, si no **el país completo** (siempre en la misma moneda).
2. Calcula el z-score modificado de Iglewicz y Hoaglin sobre `log(monto)`: `0.6745 · (x − mediana) / MAD`.
3. Revisa también las cercas de Tukey: `[Q1 − 1,5·IQR, Q3 + 1,5·IQR]`.
4. Veredicto: **alta** si |z| > 5, **revisar** si |z| > 3,5 o el monto queda fuera de las cercas, **normal** en otro caso.

`reference.json` contiene solo agregados (mediana, MAD, cuartiles y tamaño de cada grupo) y el nombre público del comprador. No contiene ningún contrato individual. Se regenera con `backend/scripts/export_reference_model.py` del [repositorio](https://github.com/yefry08/contractor-ai-platform).

## El modelo base de Daniel Duque (`bert-xgboost/`)

- **Arquitectura:** `bert-base-multilingual-cased` lee la descripción presupuestaria, y una cabeza densa (768 → 15000 → 15000 → 1500) produce 1500 rasgos. A esos rasgos se suman 54 columnas *one-hot* de campos OCDS (criterio de adjudicación, estado, número de oferentes, método de envío, categoría detallada, moneda…). XGBoost (`reg:pseudohubererror`, 1351 árboles) predice el valor en millones de USD constantes.
- **Datos:** licitaciones de servicios de Paraguay ([DNCP, API OCDS v3](https://www.contrataciones.gov.py/datos/api/v3/doc/)), montos llevados a USD y ajustados por CPI.
- **Archivos:** `model.ubj` (formato nativo de XGBoost, sin *pickle*) y `feature_names.json` con las 1554 columnas en orden.
- **Limitación importante:** los pesos de la cabeza BERT ajustada (`primero.pt`) no forman parte de esta publicación. Sin ellos no se pueden calcular los 1500 rasgos de texto, así que este XGBoost sirve para **reproducir y auditar** el trabajo original, no para puntuar contratos nuevos. Para analizar un contrato hoy, usa `analyzer.py`.
- Basado en [ofiscal/contract-transparency](https://github.com/ofiscal/contract-transparency---copia).

## Limitaciones y uso responsable

- Un veredicto «revisar» o «alta» es una **señal para mirar más de cerca**, nunca una acusación de corrupción. Hay compras legítimamente atípicas (urgencias, obras únicas, errores de carga en el portal).
- Cada país publica distinto: muestras de distinto tamaño y período (ver la sección «Datos de los datos» de la plataforma). Perú tiene muy pocos contratos.
- Los montos están en moneda local y **no se comparan entre países**.

## Cita

Equipo Contractor AI (2026). *Contractor AI: detección de anomalías de precio en contratación pública de 10 países de América Latina*. Modelo base: Daniel Duque Lozano.
