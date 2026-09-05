"""Mapeo del conector de El Salvador, contra un payload real y sin red.

Sobre el fixture: es una fila real de COMPRASAL con **los nombres de personas
sustituidos por "REDACTADO"**. La estructura se conserva intacta -- los objetos
`accionistas` y `beneficiario` siguen ahí, con sus mismas claves -- porque
justamente hay que poder probar que el conector NO los guarda. Lo que no entra
al repositorio son los nombres reales: sería incoherente excluir datos
personales de la base y después commitearlos como material de prueba.

Los datos de empresa (razón social del proveedor, institución compradora,
monto, fecha) se dejan tal cual: son de personas jurídicas y son exactamente lo
que el conector sí almacena.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import ingest_el_salvador_live as sv  # noqa: E402

ROW = json.loads(
    (Path(__file__).parent / "fixtures" / "el_salvador_row.json").read_text(encoding="utf-8")
)


@pytest.fixture
def row() -> dict:
    return json.loads(json.dumps(ROW))


def test_fixture_still_carries_the_personal_fields(row):
    """Si la fuente dejara de mandarlos, el test de exclusion pasaria por la
    razon equivocada -- verde porque no hay nada que excluir. Esto lo detecta."""
    assert row.get("accionistas"), "el fixture debe conservar la estructura"
    assert row.get("beneficiario"), "el fixture debe conservar la estructura"


def test_slim_payload_drops_personal_data(row):
    slim = sv.slim_payload(row, "Licitación competitiva")

    assert "accionistas" not in slim
    assert "beneficiario" not in slim
    # Ni anidados en el proveedor: la respuesta original los trae ahi tambien.
    assert "accionistas" not in slim["proveedor"]

    # Y nada que se parezca a un nombre de persona sobrevive en el payload.
    blob = json.dumps(slim, ensure_ascii=False)
    assert "REDACTADO" not in blob
    for key in ("primer_nombre", "primer_apellido", "apellido_casada"):
        assert key not in blob


def test_slim_payload_keeps_the_company(row):
    slim = sv.slim_payload(row, "Licitación competitiva")
    assert slim["proveedor"]["nombre"] == (row["proveedor"] or {}).get("nombre")
    assert slim["codigo_proceso"] == (row["proceso_compra"] or {}).get("codigo_proceso")
    assert slim["forma_contratacion"] == "Licitación competitiva"


def test_amount_is_usd_without_conversion(row):
    """El Salvador esta dolarizado: es el unico pais del corpus donde
    amount_usd se llena sin inventar una tasa de cambio."""
    amount = sv.to_float(row.get("monto"))
    assert amount is not None and amount > 0


def test_to_float_rejects_unusable_amounts():
    assert sv.to_float(None) is None
    assert sv.to_float("") is None
    assert sv.to_float("no-es-un-numero") is None
    assert sv.to_float("1234.5") == 1234.5


def test_parse_date_reads_the_award_date(row):
    fecha = (row["proceso_compra"] or {}).get("fecha_adjudicacion")
    assert sv.parse_date(fecha) is not None
    assert sv.parse_date(None) is None
    assert sv.parse_date("30 de febrero") is None


def test_row_id_is_the_idempotency_key(row):
    """Varias filas comparten codigo_proceso (son renglones del mismo proceso),
    asi que la clave no puede ser el codigo: tiene que ser el id de la fila."""
    assert row.get("id") is not None
    slim = sv.slim_payload(row, None)
    assert slim["row_id"] == row["id"]
