VISIT_COST_BY_TIER = {
    'Bronze': 150.0,
    'Silver': 75.0,
    'Gold': 20.0,
}


def calculate_visit_cost(insurance_tier: str, visit_type: str) -> float:
    _ = visit_type
    try:
        return VISIT_COST_BY_TIER[insurance_tier]
    except KeyError as error:
        raise ValueError('Unknown insurance tier') from error
