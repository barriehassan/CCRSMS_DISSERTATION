from django.core.exceptions import ValidationError
import re

def validate_sierra_leone_number(value):
    if not str(value).startswith("+232"):
        raise ValidationError("Phone number must start with +232.")
    if len(str(value)) != 12:
        raise ValidationError("Phone number must follow +232XXXXXXXX format.")


def validate_nin(value):
    """
    Sierra Leone NIN format:
    Example: 00F7STR2
    """
    if not value:
        return

    pattern = r'^\d{2}[A-Z]\d[A-Z]{3}\d$'
    if not re.fullmatch(pattern, value):
        raise ValidationError(
            "Invalid NIN format. Expected format: 00F7STR2"
        )


def validate_passport(value):
    """
    Sierra Leone Passport formats:
    Examples:
    - SLR124311
    - ER361085
    """
    if not value:
        return

    pattern = r'^[A-Z]{2,3}\d{6}$'
    if not re.fullmatch(pattern, value):
        raise ValidationError(
            "Invalid passport number format. Expected formats: SLR124311 or ER361085"
        )

