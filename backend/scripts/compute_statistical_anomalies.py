"""Fase 5 (ADR 0003): capa estadística de detección de anomalías,
completamente independiente de cualquier modelo NLP/LLM. Llena la tabla
`statistical_flags` (sin usar hasta ahora) y crea/completa filas de
`Anomaly` para que los contratos ingeridos sin modelo de predicción
(~8.600 de Colombia en vivo, Costa Rica y República Dominicana) tengan
también una señal de anomalía -- hoy solo Paraguay y el bulk de Colombia
la tienen, porque vienen con predicciones ya calculadas por el prototipo
original.

Metodología (fórmulas establecidas, no inventadas):
  - Z-score modificado (Iglewicz & Hoaglin): 0.6745 * (x - mediana) / MAD.
    Se marca cuando |z modificado| > 3.5 (umbral recomendado en la
    literatura para este método, más robusto que z-score clásico frente a
    outliers extremos).
  - Cercas de Tukey (método IQR clásico): se marca cuando x cae fuera de
    [Q1 - 1.5*IQR, Q3 + 1.5*IQR].

Grupo de referencia por contrato (jerarquía de fallback -- se usa el grupo
más específico que tenga suficientes datos para que la estadística tenga
sentido, si no hay suficientes se cae al siguiente nivel, más amplio):
  1. (país, comprador) si ese comprador tiene >= MIN_GROUP_SIZE contratos
  2. (país, categoría) si esa categoría tiene >= MIN_GROUP_SIZE contratos
  3. (país) -- siempre tiene suficientes datos, es el fallback final

Para contratos que YA tienen una fila de Anomaly (de la señal NLP, Paraguay
y el bulk de Colombia): se agrega `stat_component` a esa fila existente sin
tocar `nlp_component` ni `composite_score` -- las dos señales quedan
visibles por separado, que es exactamente el punto de tener una capa
independiente (ADR 0003).

Para contratos SIN fila de Anomaly: se crea una nueva SOLO si el método de
Tukey o el z-score modificado lo marca como outlier -- misma lección del
bug de umbral de la migración de Paraguay: no se marca todo como
"anómalo", solo los que de verdad se salen de su grupo de referencia.

Idempotente: al arrancar borra todas las filas de `statistical_flags` y las
recalcula desde cero (son baratas de regenerar). Las filas de `Anomaly` se
actualizan in-place o se crean solo si no existían, así que correr el
script varias veces no duplica nada.

IMPORTANTE -- corrección encontrada probando contra datos reales, no en
teoría: la primera versión de este script calculaba el z-score modificado y
el IQR directamente sobre `amount_original`. Contra un grupo real
(Costa Rica, "Según demanda") esto produjo un z-score de **258,491** para un
contrato de construcción de ~$1.4M USD comparado contra un grupo dominado
por compras chicas (mediana ~1.700 CRC, MAD ~1.700 CRC) -- técnicamente
"correcto" según la fórmula, pero un número sin sentido práctico. La causa
es conocida en estadística de datos de gasto público: los montos son casi
siempre asimétricos a la derecha (muchos contratos chicos, pocos enormes),
así que la MAD sobre valores crudos colapsa cerca de cero y cualquier
contrato grande hace explotar el ratio. La corrección estándar (no
inventada acá) es calcular la mediana/MAD/IQR sobre el **logaritmo** del
monto, no el monto crudo -- comprime la cola larga y da scores interpretables
(típicamente de un dígito para un outlier real). Se aplica log() a montos
estrictamente positivos; los <= 0 (dato inválido, ver riesgo #1 de
PLANNING.md) se excluyen de las estadísticas en vez de romper el cálculo o
inventarles un valor.
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete  # noqa: E402

from app import models  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.stats import (  # noqa: E402
    IQR_MULTIPLIER,
    MIN_GROUP_SIZE,
    ZSCORE_THRESHOLD,
    compute_group_stats,
    modified_zscore,
)


def main():
    db = SessionLocal()
    try:
        all_contracts = (
            db.query(models.Contract.id, models.Contract.country_code, models.Contract.buyer_id, models.Contract.category_code, models.Contract.amount_original)
            .filter(models.Contract.amount_original.isnot(None))
            .all()
        )
        contracts = [c for c in all_contracts if c.amount_original > 0]
        skipped_non_positive = len(all_contracts) - len(contracts)
        print(f"{len(contracts)} contratos con monto válido (> 0) para analizar "
              f"({skipped_non_positive} con monto <= 0 excluidos de las estadísticas).")

        by_buyer: dict[tuple, list[float]] = {}
        by_category: dict[tuple, list[float]] = {}
        by_country: dict[str, list[float]] = {}
        for c in contracts:
            log_amount = math.log(c.amount_original)
            if c.buyer_id:
                by_buyer.setdefault((c.country_code, c.buyer_id), []).append(log_amount)
            if c.category_code:
                by_category.setdefault((c.country_code, c.category_code), []).append(log_amount)
            by_country.setdefault(c.country_code, []).append(log_amount)

        stats_buyer = {k: compute_group_stats(v) for k, v in by_buyer.items() if len(v) >= MIN_GROUP_SIZE}
        stats_category = {k: compute_group_stats(v) for k, v in by_category.items() if len(v) >= MIN_GROUP_SIZE}
        stats_country = {k: compute_group_stats(v) for k, v in by_country.items()}

        db.execute(delete(models.StatisticalFlag))
        # Las filas de Anomaly creadas puramente por este script (sin
        # nlp_component) son 100% regenerables -- se borran y se recalculan
        # desde cero en cada corrida, para no dejar composite_score/
        # stat_component obsoletos de una corrida anterior con otra
        # metodología (pasó de verdad: la primera versión de este script no
        # usaba log() y dejó anomalías con scores de hasta 258,491 dando
        # vueltas). Las filas con nlp_component (de Paraguay/Colombia bulk)
        # NUNCA se borran acá, solo se les actualiza stat_component.
        db.execute(delete(models.Anomaly).where(models.Anomaly.nlp_component.is_(None)))
        db.commit()

        existing_anomalies = {
            row.contract_id: row
            for row in db.query(models.Anomaly).all()
        }

        created = 0
        updated = 0
        flagged_new = 0

        for c in contracts:
            log_amount = math.log(c.amount_original)
            key_buyer = (c.country_code, c.buyer_id) if c.buyer_id else None
            key_category = (c.country_code, c.category_code) if c.category_code else None

            if key_buyer in stats_buyer:
                group_stats = stats_buyer[key_buyer]
                reference_group = f"{c.country_code}:buyer:{c.buyer_id}"
            elif key_category in stats_category:
                group_stats = stats_category[key_category]
                reference_group = f"{c.country_code}:category:{c.category_code}"
            else:
                group_stats = stats_country[c.country_code]
                reference_group = f"{c.country_code}:country"

            # Todo lo de acá para abajo opera en escala logarítmica (ver nota
            # en el docstring): "median"/"mad"/"q1"/"q3"/"iqr" de group_stats
            # son de log(monto), no del monto crudo.
            z = modified_zscore(log_amount, group_stats["median"], group_stats["mad"])
            zscore_flagged = abs(z) > ZSCORE_THRESHOLD

            iqr = group_stats["iqr"]
            lower_fence = group_stats["q1"] - IQR_MULTIPLIER * iqr
            upper_fence = group_stats["q3"] + IQR_MULTIPLIER * iqr
            iqr_score = (log_amount - group_stats["q3"]) / iqr if iqr > 0 and log_amount > group_stats["q3"] else (
                (group_stats["q1"] - log_amount) / iqr if iqr > 0 and log_amount < group_stats["q1"] else 0.0
            )
            iqr_flagged = log_amount < lower_fence or log_amount > upper_fence

            db.add(models.StatisticalFlag(
                contract_id=c.id,
                method="zscore",
                reference_group=reference_group,
                score=z,
                threshold=ZSCORE_THRESHOLD,
                flagged=zscore_flagged,
            ))
            db.add(models.StatisticalFlag(
                contract_id=c.id,
                method="iqr",
                reference_group=reference_group,
                score=iqr_score,
                threshold=IQR_MULTIPLIER,
                flagged=iqr_flagged,
            ))

            existing = existing_anomalies.get(c.id)
            if existing:
                existing.stat_component = z
                updated += 1
            elif zscore_flagged or iqr_flagged:
                # log() es monótona, así que comparar en escala log da el
                # mismo resultado que comparar el monto crudo contra la
                # mediana cruda.
                anomaly_type = "overcost" if log_amount > group_stats["median"] else "undercost"
                db.add(models.Anomaly(
                    contract_id=c.id,
                    anomaly_type=anomaly_type,
                    composite_score=abs(z),
                    nlp_component=None,
                    stat_component=z,
                    llm_narrative=None,
                    confidence=None,
                    status="open",
                ))
                created += 1
                flagged_new += 1

        db.commit()
        print(f"Flags estadísticos escritos para {len(contracts)} contratos.")
        print(f"Anomalías nuevas creadas (solo estadísticas): {created}")
        print(f"Anomalías existentes (NLP) actualizadas con stat_component: {updated}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
