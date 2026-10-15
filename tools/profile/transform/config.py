"""Assembles the `cfg` mapping every panel is handed.

profile.toml carries the prose; three JSON files carry what TOML cannot express
— two rosters and the brand marks that draw one of them. Panels read all four
off a single mapping, so none of them knows which file its content came from or
has to open one.
"""


def build(profile, stack, languages, logos):
    """`cfg` — profile.toml with the three rosters folded in under fixed keys.

    `stack` is category -> tool -> pedestal level 1-5 and `languages` is
    language -> bytes; key order is draw order in both. `logos` keys tool names
    to brand marks, and a tool missing from it falls back to mono type.
    """
    return {**profile, "stack": stack, "languages": languages, "logos": logos}
