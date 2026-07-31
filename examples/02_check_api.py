"""Example: verify a library API call and show typo suggestions."""

from __future__ import annotations

from repograph_honest.mcp.tools import check_api, load_package_apis


def main() -> None:
    load_package_apis("math")

    for api in ["math.sqrt", "math.sqrtt", "math.nonexistent_thing"]:
        result = check_api(api)
        print(f"{api}: valid={result['valid']}, suggestion={result.get('suggestion')}")


if __name__ == "__main__":
    main()
