import json
import re
from typing import Dict, List


def wrap_code(code: str, lang="python") -> str:
    """Wraps code with three backticks."""
    return f"""```{lang}\n\n{code}\n```"""


def is_valid_python_script(script):
    """Check if a script is a valid Python script."""
    try:
        compile(script, "<string>", "exec")
        return True
    except SyntaxError:
        return False


def extract_json(text) -> List[Dict]:
    """Extract all JSON objects from the text. Caveat: This function cannot handle nested JSON objects."""
    json_objects = []

    # Find {} by regular expression
    matches = re.findall(r"\{.*?\}", text, re.DOTALL)

    # Try to transform string into json objects.
    for match in matches:
        try:
            json_object = json.loads(match)
            json_objects.append(json_object)
        except json.JSONDecodeError:
            pass

    return json_objects


def trim_long_string(string, threshold=5100, k=2500):
    # Check if the length of the string is longer than the threshold.
    string_len = len(string)
    if string_len > threshold:
        # Output the first k and the last k characters.
        first_k_chars = string[:k]
        last_k_chars = string[-k:]
        truncated_lengths = string_len - k * 2
        return f"{first_k_chars}\n ... [{truncated_lengths} characters truncated] ... \n{last_k_chars}"
    else:
        return string


def extract_code(text):
    """Extract python code blocks from the text."""
    parsed_codes = []

    # When code is in a text or python block
    matches = re.findall(r"```(python)?\n*(.*?)\n*```", text, re.DOTALL)
    for match in matches:
        code_block = match[1]
        parsed_codes.append(code_block)

    # When the entire text is code or backticks of the code block is missing
    if len(parsed_codes) == 0:
        matches = re.findall(r"^(```(python)?)?\n?(.*?)\n?(```)?$", text, re.DOTALL)
        if matches:
            code_block = matches[0][2]
            parsed_codes.append(code_block)

    valid_code_blocks = [c for c in parsed_codes if is_valid_python_script(c)]
    return "\n\n".join(valid_code_blocks)


def extract_text_up_to_code(text: str):
    """Extract (presumed) natural language text up to the start of the first code block, which means the analysis before writing code."""
    if "```" not in text:
        return ""
    return text[: text.find("```")].strip()
