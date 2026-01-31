"""..."""

from homeassistant.util import slugify


def create_entity_id_name(input_string: str) -> str:
    """
    Creates a normalized entity ID name from a raw input string.

    Args:
        raw_name: The raw input string to transform.

    Returns:
        The normalized entity ID name.
    """

    # Split the string at the first "."
    first_part, second_part = input_string.split(".", 1)

    # Replace non-alphanumeric characters (except "_") with "_" in both parts
    first_part = first_part.lower()
    second_part = slugify(second_part)

    # Recombine with the first "." preserved
    normalized_name = f"{first_part}.{second_part}"

    return normalized_name
