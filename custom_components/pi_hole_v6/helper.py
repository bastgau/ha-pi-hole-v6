"""..."""

import re


def create_entity_id_name(input_string: str) -> str:
    """
    Creates a normalized entity ID name from a raw input string.

    Args:
        raw_name: The raw input string to transform.

    Returns:
        The normalized entity ID name.
    """

    # Convert to lowercase
    input_string = input_string.lower()

    # Split the string at the first "."
    first_part, second_part = input_string.split(".", 1)

    # Replace non-alphanumeric characters (except "_") with "_" in both parts
    first_part = re.sub(r"[^a-z0-9]", "_", first_part)
    second_part = re.sub(r"[^a-z0-9]", "_", second_part)

    # Recombine with the first "." preserved
    cleaned = f"{first_part}.{second_part}"

    # Replace multiple "_" with a single "_"
    cleaned = re.sub(r"_+", "_", cleaned)

    return cleaned
