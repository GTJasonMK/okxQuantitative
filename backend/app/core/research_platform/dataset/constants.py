INPUT_WINDOW_SECONDS_15M = 7200
LABEL_WINDOW_SECONDS_15M = 900

LABEL_VECTOR_FIELDS = ('r_open', 'r_close', 'u', 'd')

BOUNDARY_TARGET_LABEL_DEFINITION_V1 = (
    'next_bar_15m_ohlc_reparam_from_session_seconds_v1'
)
SAMPLE_FILTER_RULE_V1 = 'single_session_strict_7200x900_v1'
