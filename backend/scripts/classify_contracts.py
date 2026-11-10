"""Stores what every contract buys (app.territories.classify_sector) in
contract_sectors, so the contract map can group the whole corpus with one
query. Rerun after loading contracts or changing the classifier; the map
classifies contracts that have no row yet when it reads them, so a missed run
only costs speed.

Everything is read first and written in one short transaction (Neon drops
connections left idle inside a long one).

    cd backend
    python scripts/classify_contracts.py
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, insert, select  # noqa: E402

from app import models  # noqa: E402
from app.contract_map import UNSPSC  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.territories import classify_sector  # noqa: E402

BATCH = 5000


def main():
    Base.metadata.create_all(engine)
    rows = []
    with SessionLocal() as db:
        stmt = select(models.Contract.id, models.Contract.title, models.Contract.description,
                      models.Contract.category_code, UNSPSC)
        for cid, title, desc, cat, unspsc in db.execute(stmt.execution_options(yield_per=2000)):
            rows.append({"contract_id": cid, "sector": classify_sector(title, desc, cat, unspsc=unspsc)})
    with SessionLocal() as db:
        db.execute(delete(models.ContractSector))
        for i in range(0, len(rows), BATCH):
            db.execute(insert(models.ContractSector), rows[i : i + BATCH])
        db.commit()
    counts = Counter(r["sector"] for r in rows)
    print(f"contratos clasificados={len(rows)} " + " ".join(f"{s}={n}" for s, n in counts.most_common()))


if __name__ == "__main__":
    main()
