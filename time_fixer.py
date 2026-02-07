# time_fixer.py

from datetime import datetime, timedelta
import pytz
import dateparser
import re


# ---------------------------------------------------
# Small NLP normalizer for messy user time text
# ---------------------------------------------------
def _normalize_time_text(text: str) -> str:
    t = text.strip().lower()

    # common spoken patterns
    replacements = {
        "by ": "",
        "around ": "",
        "about ": "",
        "at around ": "at ",
        "in the morning": " at 9am",
        "in the evening": " at 6pm",
        "in the afternoon": " at 3pm",
        "at night": " at 9pm",
        "tonite": "tonight",
    }

    for k, v in replacements.items():
        t = t.replace(k, v)

    # fix things like:
    # "tomorrow morning by 10 am"
    # -> "tomorrow at 10 am"
    t = re.sub(
        r"(today|tomorrow)\s+morning\s+(?:by|at)\s+",
        r"\1 at ",
        t
    )

    t = re.sub(
        r"(today|tomorrow)\s+evening\s+(?:by|at)\s+",
        r"\1 at ",
        t
    )

    t = re.sub(
        r"(today|tomorrow)\s+afternoon\s+(?:by|at)\s+",
        r"\1 at ",
        t
    )

    return t


# ---------------------------------------------------
# Main function
# ---------------------------------------------------
def fix_time_from_text(time_text, user_timezone="UTC"):
    """
    Convert natural language time to ISO 8601 in user's timezone.

    Returns:
        ISO string like '2026-02-06T10:00:00+01:00'
        or None
    """

    if not time_text or not time_text.strip():
        return None

    user_tz = pytz.timezone(user_timezone)
    base_dt = datetime.now(user_tz)

    raw_text = time_text.strip()
    norm_text = _normalize_time_text(raw_text)

    # ------------------------------------------------
    # Relative expressions:
    #   2 days after 5th Feb
    #   a week before 3rd of April
    # ------------------------------------------------
    match = re.search(
        r'(?i)(\d+|a)\s*(day|week|month|year)s?\s*(before|after)\s*(.+)',
        norm_text
    )

    if match:
        qty_raw, unit, direction, reference_text = match.groups()

        qty = 1 if qty_raw.lower() == "a" else int(qty_raw)

        ref_dt = dateparser.parse(
            reference_text,
            settings={
                "TIMEZONE": str(user_tz),
                "RETURN_AS_TIMEZONE_AWARE": True,
                "PREFER_DATES_FROM": "future",
                "RELATIVE_BASE": base_dt
            }
        )

        if not ref_dt:
            return None

        if unit == "day":
            delta = timedelta(days=qty)
        elif unit == "week":
            delta = timedelta(weeks=qty)
        elif unit == "month":
            delta = timedelta(days=qty * 30)
        else:
            delta = timedelta(days=qty * 365)

        if direction.lower() == "before":
            fixed_dt = ref_dt - delta
        else:
            fixed_dt = ref_dt + delta

        return fixed_dt.isoformat()

    # ------------------------------------------------
    # Normal dateparser pass (with normalized text)
    # ------------------------------------------------
    dt = dateparser.parse(
        norm_text,
        settings={
            "TIMEZONE": str(user_tz),
            "RETURN_AS_TIMEZONE_AWARE": True,
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": base_dt
        }
    )

    if not dt:
        return None

    return dt.isoformat()
