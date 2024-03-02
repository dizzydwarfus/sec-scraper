import re


def convert_keys_to_lowercase(d):
    """Recursively convert all keys in a dictionary to lowercase.

    Args:
        d (dict): Dictionary to convert

    Returns:
        dict: Dictionary with all keys converted to lowercase
    """
    new_dict = {}
    for k, v in d.items():
        if isinstance(v, dict):
            v = convert_keys_to_lowercase(v)
        new_key = re.sub(r"[^a-zA-Z0-9]", "", k.lower())
        new_dict[new_key] = v
    return new_dict


def indexify_url(folder_url: str) -> str:
    """Converts url to index url.

    Args:
        url (str): url to convert to index url

    Returns:
        str: index url
    """
    return folder_url + "/index.json"


def reverse_standard_mapping(standard_name_mapping: dict):
    reverse_mapping = {}
    for standard_name, xbrl_tags in standard_name_mapping.items():
        for tag in xbrl_tags:
            reverse_mapping[tag] = standard_name

    return reverse_mapping
