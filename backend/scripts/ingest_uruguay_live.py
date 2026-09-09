"""Ingesta EN VIVO de Uruguay (ONCP - Oficina Nacional de Contrataciones Públicas).

Fuente: Oficina Nacional de Contrataciones Públicas (ONCP) de Uruguay.
Este script facilita la ingesta de datos de contrataciones públicas de Uruguay
desde el portal oficial de la ONCP.

Estado actual: Scaffold para futuras integraciones con la API de ONCP.
Se espera verificar endpoint real y desarrollar mapeo de campos antes de
producción.

Nota: Uruguay tiene disponibilidad de datos públicos de contrataciones. El mapeo
exacto de campos al esquema interno de este proyecto (OCDS) se debe verificar
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

COUNTRY_CODE = "UY"
# Placeholder: Actualizar con endpoint real cuando esté verificado
BASE_URL = "https://www.oncp.gub.uy/api"


def main():
    """Initialize country record for Uruguay."""
    parser = argparse.ArgumentParser(description="Ingesta en vivo de Uruguay (ONCP).")
    parser.add_argument("--max-records", type=int, default=100)
    args = parser.parse_args()

    Base.metadata.create_all(engine)
    db = SessionLocal()

    try:
        country = db.get(models.Country, COUNTRY_CODE)
        if country is None:
            country = models.Country(
                code=COUNTRY_CODE,
                name="Uruguay",
                ocds_portal_url="https://www.oncp.gub.uy",
                schema_variant="oncp-derivado",
                ingestion_method="api",
                active=True,
            )
            db.add(country)
            db.commit()
            print(f"✓ Country initialized: {country.name} ({country.code})")
        else:
            print(f"✓ Country already exists: {country.name} ({country.code})")

    except Exception as e:
        print(f"✗ Error initializing Uruguay country record: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
