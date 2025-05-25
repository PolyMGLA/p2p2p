import inspect

def get_error_context():
    frame = inspect.currentframe().f_back.f_back
    return {
        'file': frame.f_code.co_filename,
        'line': frame.f_lineno,
        'function': frame.f_code.co_name
    }

def printf(cap: str, ln: int):
    left = (ln - len(cap)) // 2
    print("=" * (left - 1) + " " + cap + " " + "=" * (ln - len(cap) - left - 1))