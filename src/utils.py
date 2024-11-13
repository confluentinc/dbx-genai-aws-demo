import json


def is_json(some_string):
    some_string = some_string.strip()
    if not some_string.startswith("{") or not some_string.endswith("}"):
        return False
    try:
        json.loads(some_string)
    except ValueError:
        return False
    return True
