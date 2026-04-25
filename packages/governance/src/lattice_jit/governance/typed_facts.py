ALLOWED_FACT_TYPES = {
    "decision",
    "constraint",
    "api_signature",
    "owner",
    "incident",
}


def validate_fact_type(fact_type: str) -> bool:
    return fact_type in ALLOWED_FACT_TYPES
