# Synthetic redaction input only; not a real credential.
# api_key = "sk-SYNTHETIC_FIXTURE_NOT_A_REAL_CREDENTIAL"
def f(values):
    if not values:
        return 0
    return sum(values) / len(values)
