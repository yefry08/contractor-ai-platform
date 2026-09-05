"""Mapeo del conector de Perú, contra un payload real y sin red.

Primer test de ingesta del proyecto. Hasta ahora los cuatro conectores de país
no tenían ninguno: si un portal cambiaba la forma de su respuesta, el síntoma
era una corrida que "termina bien" e inserta contratos con el campo equivocado,
no un test en rojo.

El fixture (`fixtures/peru_releases.json`) son dos releases reales bajados de
`contratacionesabiertas.oece.gob.pe` el 2026-09-04: uno adjudicado y uno que
todavía va por la etapa de convocatoria. Se guarda tal cual llegó, así que si
la fuente cambia de forma, estos tests siguen describiendo lo que había cuando
se escribió el conector.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import ingest_peru_live as peru  # noqa: E402

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "peru_releases.json").read_text(encoding="utf-8")
)


@pytest.fixture
def awarded() -> dict:
    return FIXTURE["awarded"]


@pytest.fixture
def not_awarded() -> dict:
    return FIXTURE["not_awarded"]


def test_pick_award_returns_none_without_awards(not_awarded):
    # La mayoria del feed es convocatoria sin adjudicar. Ese caso se saltea, no
    # se ingiere con monto cero ni con el valor referencial.
    assert peru.pick_award(not_awarded) is None


def test_pick_award_takes_the_awarded_amount(awarded):
    award = peru.pick_award(awarded)
    assert award is not None
    assert award["value"]["amount"] > 0
    assert award["value"]["currency"] == "PEN"


def test_awarded_amount_is_not_the_reference_value(awarded):
    """El punto metodologico del conector, en un test.

    `tender.value` es el presupuesto estimado antes de licitar y `award.value`
    lo que se adjudico: son cifras distintas. Mezclarlas con los montos
    adjudicados del resto de los paises romperia /analyze/compare en silencio,
    porque los numeros seguirian siendo plausibles.
    """
    award = peru.pick_award(awarded)
    tender_value = awarded["tender"]["value"]["amount"]
    assert award["value"]["amount"] != tender_value


def test_pick_award_prefers_the_largest_lot():
    release = {
        "awards": [
            {"value": {"amount": 100.0, "currency": "PEN"}},
            {"value": {"amount": 900.0, "currency": "PEN"}},
            {"value": {"amount": 500.0, "currency": "PEN"}},
        ]
    }
    assert peru.pick_award(release)["value"]["amount"] == 900.0


def test_pick_award_ignores_unusable_amounts():
    release = {
        "awards": [
            {"value": {"amount": None}},
            {"value": {"amount": "no-es-un-numero"}},
            {"value": {}},
            {},
        ]
    }
    assert peru.pick_award(release) is None


def test_suppliers_carry_the_ruc(awarded):
    """El RUC es lo que hace util a Peru para el analisis de proveedores.

    Los otros cuatro paises no traen proveedor identificado, asi que
    "Favoritismo de Proveedores" hoy agrupa por comprador. Un nombre suelto no
    alcanza: se repite escrito de formas distintas. El RUC si identifica.
    """
    award = peru.pick_award(awarded)
    suppliers = peru.suppliers_of(awarded, award)

    assert suppliers, "el release adjudicado del fixture tiene proveedor"
    first = suppliers[0]
    assert first["name"]
    assert first["scheme"] == "PE-RUC"
    assert first["identifier"] and first["identifier"].isdigit()


def test_slim_payload_keeps_supplier_and_cubso(awarded):
    award = peru.pick_award(awarded)
    slim = peru.slim_payload(awarded, award)

    assert slim["ocid"] == awarded["ocid"]
    assert slim["suppliers"][0]["scheme"] == "PE-RUC"

    item = slim["items"][0]
    assert item["classification_scheme"] == "CUBSO"
    assert item["classification_description"]

    # Ambos valores quedan guardados para poder auditar despues la diferencia
    # entre lo presupuestado y lo adjudicado.
    assert slim["award_value"] == award["value"]["amount"]
    assert slim["tender_value"] == awarded["tender"]["value"]["amount"]


def test_slim_payload_is_far_smaller_than_the_release(awarded):
    """Guardar el release entero costaba 10,5 KB por contrato -- quince veces
    lo que ocupa Republica Dominicana, ~26 MB proyectados sobre un plan
    gratuito, y el 90% era `parties`/`documents` que ninguna consulta lee."""
    award = peru.pick_award(awarded)
    full = len(json.dumps(awarded, ensure_ascii=False).encode())
    slim = len(json.dumps(peru.slim_payload(awarded, award), ensure_ascii=False).encode())
    assert slim < full / 5, f"slim={slim}B full={full}B"


def test_parse_date_handles_the_feeds_offset_format():
    assert peru.parse_date("2026-09-03T00:00:00-05:00").isoformat() == "2026-09-03"
    assert peru.parse_date(None) is None
    assert peru.parse_date("") is None
    assert peru.parse_date("marzo de 2026") is None
