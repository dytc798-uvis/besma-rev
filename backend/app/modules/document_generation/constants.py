from __future__ import annotations


class GenerationRule:
    ADHOC_MANUAL = "ADHOC_MANUAL"
    ON_PERIOD_START = "ON_PERIOD_START"
    ON_PERIOD_END = "ON_PERIOD_END"
    ON_DAY_OF_PERIOD = "ON_DAY_OF_PERIOD"
    DAILY = "DAILY"


class DocumentSourceType:
    AUTO = "AUTO"
    MANUAL = "MANUAL"
    WORKPLAN_ASSEMBLE = "WORKPLAN_ASSEMBLE"
