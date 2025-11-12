"""
Version utility functions.
"""


def get_version() -> str:
    """
    Get the current version of Entmoot.

    Returns:
        str: The version string.
    """
    return "0.1.0"


def format_version_info() -> dict[str, str]:
    """
    Get formatted version information.

    Returns:
        dict[str, str]: Dictionary containing version information.
    """
    return {
        "version": get_version(),
        "project": "Entmoot",
        "description": "AI-driven site layout automation",
    }
