"""Questions and complaints about procurement processes.

Contractor AI receives them, gives the filer a tracking code, and always
points to the official channels where a complaint has legal effect: the
procurement agency (observations and challenges inside the process) and the
oversight body (corruption complaints). It is a first stop that helps
someone find the right door and lets the team spot patterns -- never a
substitute for those channels, and never a public pillory: inquiry text is
not published.
"""

from __future__ import annotations

import secrets

from .tenders import OFFICIAL_PORTALS

# Oversight / anti-corruption bodies. Each URL answered 200 on 2026-10-24
# except Guatemala's Contraloría, whose firewall answers 403 to scripts
# (the site loads in a browser; Guatecompras does the same).
OVERSIGHT: dict[str, dict[str, str]] = {
    "PY": {"name": "Contraloría General de la República", "url": "https://www.contraloria.gov.py/"},
    "CO": {"name": "Secretaría de Transparencia", "url": "https://www.secretariatransparencia.gov.co/"},
    "CR": {"name": "Contraloría General de la República", "url": "https://www.cgr.go.cr/"},
    "DO": {"name": "Línea 311 — Denuncias, quejas y reclamaciones", "url": "https://311.gob.do/"},
    "SV": {"name": "Corte de Cuentas de la República", "url": "https://www.cortedecuentas.gob.sv/"},
    "PE": {"name": "Contraloría General de la República", "url": "https://www.gob.pe/contraloria"},
    "BR": {"name": "Fala.BR — Controladoria-Geral da União", "url": "https://falabr.cgu.gov.br/"},
    "UY": {"name": "JUTEP — Junta de Transparencia y Ética Pública", "url": "https://www.gub.uy/junta-transparencia-etica-publica/"},
    "CL": {"name": "Contraloría General de la República", "url": "https://www.contraloria.cl/"},
    "GT": {"name": "Contraloría General de Cuentas", "url": "https://www.contraloria.gob.gt/"},
}

KINDS = ("consulta", "reclamo", "alerta")
STATUSES = ("recibido", "en_revision", "derivado", "cerrado")

# No 0/O, 1/I/L: the code gets read aloud and typed back.
_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def new_code() -> str:
    return "CAI-" + "".join(secrets.choice(_ALPHABET) for _ in range(8))


def channels_for(country_code: str) -> list[dict[str, str]]:
    out = []
    if country_code in OFFICIAL_PORTALS:
        portal = OFFICIAL_PORTALS[country_code]
        out.append({"role": "procurement", "name": portal["name"], "url": portal["url"]})
    if country_code in OVERSIGHT:
        body = OVERSIGHT[country_code]
        out.append({"role": "oversight", "name": body["name"], "url": body["url"]})
    return out
