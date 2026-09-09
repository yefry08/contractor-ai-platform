"""Automatic contract category classification.

Classifies contracts into UNSPSC/CUBSO categories:
- goods (productos/bienes)
- services (servicios)
- works (obras/construcción)
- other (otros)

Uses keyword matching + confidence scoring. No ML model dependencies -- pure
deterministic rules work as well for procurement data (mostly technical terms).

Supports all 8 countries (PY, CO, CR, DO, SV, PE, BR, UY) with multilingual keywords.
"""

from dataclasses import dataclass
from enum import Enum


class CategoryCode(str, Enum):
    """Standard procurement categories."""
    GOODS = "goods"
    SERVICES = "services"
    WORKS = "works"
    OTHER = "other"


@dataclass
class ClassificationResult:
    """Result of contract category classification."""
    category: CategoryCode
    confidence: float  # 0-1: confidence in classification
    matched_keywords: list[str]
    explanation: str


# Multilingual keywords for 6 countries
GOODS_KEYWORDS = {
    # Spanish common terms
    "producto", "productos", "bien", "bienes", "material", "materiales",
    "equipo", "equipos", "suministro", "suministros", "comida", "alimento",
    "medicin", "medicament", "combustible", "repuesto", "parte", "componente",
    "software", "licencia", "hardware", "computadora", "computador",
    # Specific to countries
    "acero", "cemento", "vidrio", "plástico", "metal", "eléctric",
    "maquinaria", "herramienta", "vehículo", "mueble", "papel", "tinta",
    "compra", "adquisición", "provisión", "entrega", "suministrador",
    # UNSPSC goods divisions
    "90000", "60000", "70000", "80000", "30000", "40000", "50000",
}

SERVICES_KEYWORDS = {
    # Spanish common terms
    "servicio", "servicios", "consultoría", "consultor", "asesoría", "asesor",
    "mantenimiento", "reparación", "limpieza", "seguridad", "vigilancia",
    "transporte", "logística", "envío", "publicidad", "marketing", "diseño",
    "capacitación", "formación", "entrenamiento", "educación", "docencia",
    "asesoramiento", "gestión", "administración", "auditoría", "contabilidad",
    "legal", "abogado", "notaría", "traducción", "interpretación",
    "telecomunicación", "comunicación", "internet", "telefonía", "postal",
    "energía", "agua", "electricidad", "gas", "acueducto",
    "salud", "médico", "hospital", "clínica", "farmacia", "doctor",
    "turismo", "hotel", "hospedaje", "alojamiento", "viaje",
    "recreación", "entretenimiento", "evento", "conferencia", "seminario",
    # UNSPSC services divisions
    "81000", "82000", "83000", "84000", "85000", "86000", "87000", "88000", "89000",
}

WORKS_KEYWORDS = {
    # Spanish common terms
    "obra", "obras", "construcción", "construir", "edificio", "edificación",
    "infraestructura", "carretera", "puente", "túnel", "acueducto", "presa",
    "demolición", "excavación", "cimentación", "estructura", "refuerzo",
    "instalación", "cableado", "plomería", "fontanería", "electricista",
    "renovación", "rehabilitación", "remodelación", "reforma", "mejora",
    "pintura", "acabado", "revestimiento", "cubierta", "techo",
    "pavimentación", "asfalto", "concreto", "piedra", "adoquín",
    "jardinería", "paisajismo", "áreas verdes", "reforestación",
    "mantenimiento vial", "limpieza de calles", "alcantarillado",
    # UNSPSC works divisions
    "30200", "30300", "30400", "30500", "30600", "30700",
    # General construction terms
    "proyecto", "contrata", "contratista", "ingeniero", "arquitecto",
    "supervisor", "superintendente", "maestro", "obrero", "peón",
}

# Reduced penalty keywords (exclude from confidence)
PENALTY_KEYWORDS = {
    "plan", "sistema", "programa", "proyecto", "propuesta",  # Could be any category
    "estudio", "análisis", "evaluación", "diagnóstico",  # Meta-work
    "desarrollar", "crear", "diseñar", "elaborar",  # Generic verbs
}


def normalize_text(text: str) -> str:
    """Normalize text for keyword matching."""
    return text.lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")


def extract_keywords_from_text(text: str) -> list[str]:
    """Extract individual keywords from text (split on common separators)."""
    normalized = normalize_text(text)
    # Split on punctuation and whitespace, keep only word-like tokens
    import re
    tokens = re.findall(r"\b[a-záéíóúñ]+\b", normalized)
    return [t for t in tokens if len(t) >= 3]  # Require min 3 chars


def classify_contract(title: str = "", description: str = "", text: str = "") -> ClassificationResult:
    """Classify a contract into a category.

    Args:
        title: Contract title
        description: Contract description
        text: Full contract text

    Returns:
        ClassificationResult with category, confidence, matched keywords, explanation
    """
    # Combine all text with weights (title most important)
    combined = f"{title} {title} {description} {text}"
    tokens = extract_keywords_from_text(combined)

    # Count matches by category
    goods_matches = []
    services_matches = []
    works_matches = []

    for token in tokens:
        # Check for exact keyword matches or prefixes
        for keyword in GOODS_KEYWORDS:
            if token.startswith(keyword[:4]):  # Prefix match (e.g., "medicin" matches "medicina", "medicamento")
                goods_matches.append(keyword)
                break

        for keyword in SERVICES_KEYWORDS:
            if token.startswith(keyword[:4]):
                services_matches.append(keyword)
                break

        for keyword in WORKS_KEYWORDS:
            if token.startswith(keyword[:4]):
                works_matches.append(keyword)
                break

    # Remove penalty keywords that reduce confidence
    penalty_count = sum(1 for token in tokens if token in PENALTY_KEYWORDS)

    # Determine category by highest match count
    match_counts = {
        CategoryCode.GOODS: len(goods_matches),
        CategoryCode.SERVICES: len(services_matches),
        CategoryCode.WORKS: len(works_matches),
    }

    max_category = max(match_counts, key=match_counts.get)
    max_count = match_counts[max_category]
    total_matches = sum(match_counts.values())

    # Calculate confidence
    if total_matches == 0:
        confidence = 0.0
        explanation = "No se encontraron palabras clave de categoría"
        matched_keywords = []
        category = CategoryCode.OTHER
    else:
        # Confidence = (matches in winning category) / (total matches) - penalty
        raw_confidence = max_count / total_matches if total_matches > 0 else 0
        penalty = min(0.2, penalty_count * 0.05)  # Up to -20% penalty
        confidence = max(0.0, raw_confidence - penalty)

        if max_category == CategoryCode.GOODS:
            matched_keywords = goods_matches[:5]
            category = CategoryCode.GOODS
            explanation = f"Clasificado como producto/bien ({max_count} coincidencias de palabras clave)"
        elif max_category == CategoryCode.SERVICES:
            matched_keywords = services_matches[:5]
            category = CategoryCode.SERVICES
            explanation = f"Clasificado como servicio ({max_count} coincidencias de palabras clave)"
        else:
            matched_keywords = works_matches[:5]
            category = CategoryCode.WORKS
            explanation = f"Clasificado como obra/construcción ({max_count} coincidencias de palabras clave)"

    return ClassificationResult(
        category=category,
        confidence=confidence,
        matched_keywords=matched_keywords,
        explanation=explanation
    )


def get_cubso_mapping(category: CategoryCode) -> dict[str, str]:
    """Return CUBSO classification ranges for a category.

    CUBSO (Clasificación Uniforme de Bienes y Servicios del Estado) is used
    in Colombia, Peru, and other countries. Returns common ranges.
    """
    mappings = {
        CategoryCode.GOODS: {
            "80000-89999": "Bienes y suministros",
            "30000-39999": "Productos de tecnología",
            "60000-69999": "Materiales de construcción",
            "90000-99999": "Equipos y maquinaria",
        },
        CategoryCode.SERVICES: {
            "20000-29999": "Servicios profesionales",
            "70000-79999": "Servicios de mantenimiento",
            "81000-89999": "Servicios técnicos",
            "85000-86999": "Servicios de salud y educación",
        },
        CategoryCode.WORKS: {
            "30200-30799": "Obras de construcción",
            "30800-30999": "Trabajos especializados",
            "31000-31999": "Servicios de ingeniería",
        },
        CategoryCode.OTHER: {
            "10000-19999": "Diversos",
        },
    }
    return mappings.get(category, {})


def enrich_contract_with_classification(contract_dict: dict, min_confidence: float = 0.5) -> dict:
    """Enrich a contract dict with auto-classification.

    Args:
        contract_dict: Contract data with 'title', 'description', 'raw_text' fields
        min_confidence: Only set category if confidence >= this threshold

    Returns:
        contract_dict with added 'auto_category_code', 'auto_category_confidence', 'auto_category_explanation'
    """
    title = contract_dict.get("title", "")
    description = contract_dict.get("description", "")
    text = contract_dict.get("raw_text", "")

    result = classify_contract(title, description, text)

    if result.confidence >= min_confidence:
        contract_dict["auto_category_code"] = result.category.value
        contract_dict["auto_category_confidence"] = result.confidence
        contract_dict["auto_category_explanation"] = result.explanation
    else:
        contract_dict["auto_category_code"] = None
        contract_dict["auto_category_confidence"] = result.confidence
        contract_dict["auto_category_explanation"] = f"Confianza insuficiente ({result.confidence:.1%}): {result.explanation}"

    return contract_dict
