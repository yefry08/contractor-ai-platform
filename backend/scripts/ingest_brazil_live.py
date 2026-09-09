"""Ingesta EN VIVO de Brasil (ComprasGov Portal).

Fuente: Portal de Compras do Governo Federal (gov.br/compras).
Este script facilita la ingesta de datos de contrataciones públicas de Brasil
desde el portal oficial ComprasGov.

Estado actual: Scaffold para futuras integraciones con la API de ComprasGov.
Se espera verificar endpoint real y desarrollar mapeo de campos antes de
producción.

Nota: El portal ComprasGov tiene una API disponible, pero el mapeo exacto
de campos al esquema interno de este proyecto (OCDS) se debe verificar
en el momento de la implementación.
"""

import argparse
import sys
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import models  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402

COUNTRY_CODE = "BR"
# Placeholder: Actualizar con endpoint real cuando esté verificado
BASE_URL = "https://www.gov.br/compras/pt-br/api"


def main():
    """Initialize country record for Brazil."""
    parser = argparse.ArgumentParser(description="Ingesta en vivo de Brasil (ComprasGov).")
    parser.add_argument("--max-records", type=int, default=100)
    args = parser.parse_args()

    Base.metadata.create_all(engine)
    db = SessionLocal()

    try:
        country = db.get(models.Country, COUNTRY_CODE)
        if country is None:
            country = models.Country(
                code=COUNTRY_CODE,
                name="Brasil",
                ocds_portal_url="https://www.gov.br/compras/pt-br",
                schema_variant="comprasgov-derivado",
                ingestion_method="api",
                active=True,
            )
            db.add(country)
            db.commit()
            print(f"✓ Country initialized: {country.name} ({country.code})")
        else:
            print(f"✓ Country already exists: {country.name} ({country.code})")

    except Exception as e:
        print(f"✗ Error initializing Brazil country record: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
