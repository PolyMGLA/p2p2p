def printf(cap: str, ln: int):
    left = (ln - len(cap)) // 2
    print("=" * (left - 1) + " " + cap + " " + "=" * (ln - len(cap) - left - 1))