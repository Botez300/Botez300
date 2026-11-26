"""Report schema v1.0, inferred from the TEST_ONLY fixtures (no official spec was available)."""
VALID_STATUSES = {"VERIFIED"}                       # only status allowed into the trading pipeline
KNOWN_STATUSES = {"TEST_ONLY", "DRAFT", "VERIFIED", "REJECTED", "EXPIRED"}
NULLABLE_TS = {"type": ["string", "null"], "format": "date-time"}

REPORT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["schema_version", "scanner_rules_version", "report_id", "report_type",
                 "generated_at", "market_data_as_of", "valid_until", "market_session",
                 "market_regime", "leading_sectors", "leading_industries",
                 "publication_status", "test_only", "research_only", "execution_authorized",
                 "sources", "strategy_sections", "candidates", "missing_data"],
    "properties": {
        "schema_version": {"const": "1.0"},
        "scanner_rules_version": {"type": ["string", "null"]},
        "report_id": {"type": "string", "pattern": r"^[A-Z0-9_\-\.]{3,80}$"},
        "report_type": {"enum": ["DAILY", "WEEKLY"]},
        "generated_at": NULLABLE_TS, "market_data_as_of": NULLABLE_TS, "valid_until": NULLABLE_TS,
        "market_session": {"type": "string"},
        "market_regime": {"type": ["string", "null"]},
        "leading_sectors": {"type": "array", "items": {"type": "string"}},
        "leading_industries": {"type": "array", "items": {"type": "string"}},
        "publication_status": {"enum": sorted(KNOWN_STATUSES)},
        "test_only": {"type": "boolean"},
        "research_only": {"type": "boolean"},
        "execution_authorized": {"type": "boolean"},
        "sources": {"type": "array"},
        "strategy_sections": {"type": "array"},
        "candidates": {"type": "array", "items": {"type": "object", "required": ["symbol"]}},
        "missing_data": {"type": "array", "items": {"type": "string"}},
    },
}
# Fields that must be non-null for a report to be tradeable.
MANDATORY_NON_NULL = ["scanner_rules_version", "generated_at", "market_data_as_of",
                      "valid_until", "market_regime"]
