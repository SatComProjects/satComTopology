from datetime import datetime


def parse_date(date_str: str) -> datetime:
    """
    Tries to parse the date in multiple formats.
    """
    date_formats = [
        "%d/%m/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%fZ",
    ]

    for fmt in date_formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue  # Try the next format
    raise ValueError(f"Unrecognized date format: {date_str}")
