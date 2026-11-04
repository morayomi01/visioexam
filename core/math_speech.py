"""Convert common written math notation into clearer speech text.

This only changes the spoken copy of a question. The on-screen/original
question and the answer stored for scoring remain unchanged.
"""

import re


def _read_braced(text: str, start: int) -> tuple[str, int] | None:
    if start >= len(text) or text[start] != "{":
        return None
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:index], index + 1
    return None


def _expand_latex_groups(text: str) -> str:
    """Expand common LaTeX fractions and roots, including nested groups."""
    result = []
    index = 0
    commands = (r"\frac", r"\dfrac", r"\tfrac", r"\sqrt")
    while index < len(text):
        command = next((c for c in commands if text.startswith(c, index)), None)
        if command is None:
            result.append(text[index])
            index += 1
            continue
        cursor = index + len(command)
        if command == r"\sqrt" and cursor < len(text) and text[cursor] == "[":
            # Read indexed roots using the conventional square/cube-root names.
            end_index = text.find("]", cursor + 1)
            if end_index >= 0:
                root_index = text[cursor + 1:end_index]
                group = _read_braced(text, end_index + 1)
                if group:
                    inside, after = group
                    root_name = {"2": "square root", "3": "cube root"}.get(
                        root_index, f"{root_index} root"
                    )
                    result.append(f"{root_name} of {math_to_speech(inside)}")
                    index = after
                    continue
        first = _read_braced(text, cursor)
        if not first:
            result.append(text[index])
            index += 1
            continue
        numerator_or_radicand, after_first = first
        if command == r"\sqrt":
            result.append(f"square root of {math_to_speech(numerator_or_radicand)}")
            index = after_first
            continue
        second = _read_braced(text, after_first)
        if not second:
            result.append(text[index])
            index += 1
            continue
        denominator, after_second = second
        result.append(
            f"{math_to_speech(numerator_or_radicand)} over "
            f"{math_to_speech(denominator)}"
        )
        index = after_second
    return "".join(result)


def math_to_speech(text: str) -> str:
    """Speak common equations in conventional math wording instead of symbols."""
    if not text:
        return text

    spoken = text
    for delimiter in (r"\[", r"\]", r"\(", r"\)", "$$", "$" ):
        spoken = spoken.replace(delimiter, " ")
    spoken = _expand_latex_groups(spoken)

    latex_symbols = {
        r"\cdot": " times ", r"\times": " times ", r"\div": " divided by ",
        r"\pm": " plus or minus ", r"\leq": " is less than or equal to ",
        r"\geq": " is greater than or equal to ", r"\neq": " is not equal to ",
        r"\approx": " is approximately equal to ", r"\pi": " pi ",
        r"\infty": " infinity ", r"\sum": " sum of ", r"\int": " integral of ",
        r"\alpha": " alpha ", r"\beta": " beta ", r"\theta": " theta ",
        r"\sin": " sine ", r"\cos": " cosine ", r"\tan": " tangent ",
        r"\log": " log ", r"\ln": " natural log ",
    }
    for symbol, wording in latex_symbols.items():
        spoken = spoken.replace(symbol, wording)

    # Superscript characters commonly used in plain-text question banks.
    superscripts = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")
    def unicode_power(match):
        base, exponent = match.groups()
        words = {"2": "squared", "3": "cubed"}
        if len(exponent) == 1 and exponent in words:
            return f"{base} {words[exponent]}"
        return f"{base} to the power {exponent.translate(superscripts)}"
    spoken = re.sub(r"([A-Za-z0-9)]+)([⁰¹²³⁴⁵⁶⁷⁸⁹]+)", unicode_power, spoken)

    def caret_power(match):
        base = match.group(1)
        exponent = match.group(2) or match.group(3)
        words = {"2": "squared", "3": "cubed"}
        if exponent in words:
            return f"{base} {words[exponent]}"
        return f"{base} to the power {exponent}"
    spoken = re.sub(
        r"([A-Za-z0-9)]+)\s*\^\s*(?:\{([^{}]+)\}|([A-Za-z0-9+-]+))",
        caret_power,
        spoken,
    )

    def subscript(match):
        return f"{match.group(1)} sub {match.group(2) or match.group(3)}"
    spoken = re.sub(r"([A-Za-z0-9)]+)_(?:\{([^{}]+)\}|([A-Za-z0-9]+))", subscript, spoken)

    spoken = re.sub(r"√\s*\(([^()]*)\)", r"square root of \1", spoken)
    spoken = re.sub(r"√\s*([A-Za-z0-9]+)", r"square root of \1", spoken)
    spoken = re.sub(r"\\sqrt\s*([A-Za-z0-9]+)", r"square root of \1", spoken)

    # Turn common numeric fractions and operations into ordinary spoken math.
    spoken = re.sub(r"(?<![\w.])(\d+)\s*/\s*(\d+)(?![\w.])", r"\1 over \2", spoken)
    spoken = re.sub(r"(?<=\d)\s*-\s*(?=\d)", " minus ", spoken)
    spoken = re.sub(r"(?<=[A-Za-z])\s+-\s+(?=[A-Za-z0-9(])", " minus ", spoken)
    replacements = {
        "×": " times ", "÷": " divided by ", "·": " times ",
        "≤": " is less than or equal to ", "≥": " is greater than or equal to ",
        "≠": " is not equal to ", "≈": " is approximately equal to ",
        "±": " plus or minus ", "∞": " infinity ", "π": " pi ",
        "=": " equals ", "+": " plus ",
        "<": " is less than ", ">": " is greater than ",
    }
    for symbol, wording in replacements.items():
        spoken = spoken.replace(symbol, wording)

    return re.sub(r"\s+", " ", spoken).strip()
