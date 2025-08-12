import logging
import re
from colored import fg, attr
from enum import Enum
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def pretty_traceback(error: BaseException, comment=""):
    file = error.__traceback__.tb_frame.f_code.co_filename
    line = error.__traceback__.tb_lineno
    # tb = "".join(traceback.format_exception_only(error))
    tb = str(error.__class__).replace("<class '", "").replace("'>", "")
    output = (
        f"{fg('red_1')}Error in {fg('red')}{file}{fg('red_1')} on line "
        f"{fg('red')}{line}{fg('red_1')}:\n  {tb}: {fg('red')}{error}{attr('reset')}"
    )
    if comment != "":
        output = (
            output
            + f"\n{fg('blue_1')}Additional comment: {fg('blue')}{comment}{attr('reset')}"
        )
    return output


def small_traceback(error: BaseException, comment=""):
    file = error.__traceback__.tb_frame.f_code.co_filename
    line = error.__traceback__.tb_lineno
    # tb = "".join(traceback.format_exception_only(error))
    tb = str(error.__class__).replace("<class '", "").replace("'>", "")
    output = f"Error in {file} on line {line}:\n" f"{tb}: {error}"
    if comment != "":
        output = output + f"\nAdditional comment: {comment}"
    return output


class ReturnType(Enum):
    RESULT = "result"
    ELEMENT = "element"
    EXISTS = "exists"


def keys_exists(element: dict, keys: tuple, returntype: ReturnType = ReturnType.EXISTS):
    """
    Check if *keys (nested) exists in `element` (dict).

    args:
        element: The dictionary to check.
        keys: The keys to check for existence one after another.
        returntype: The type of return value.
    """
    try:
        if not isinstance(element, dict):
            raise AttributeError("keys_exists() expects dict as first argument.")
        if not isinstance(keys, tuple):
            raise AttributeError("keys_exists() expects tuple as second argument.")

        _element = element
        for key in keys:
            try:
                _element = _element[key]
                # print(_element)
            except (KeyError, IndexError, TypeError):
                # print(pretty_traceback(error))
                # print(f"key: {key}")
                match returntype:
                    case ReturnType.RESULT:
                        return None
                    case ReturnType.ELEMENT:
                        return []
                    case _:
                        return False
        match returntype:
            case ReturnType.RESULT:
                return _element
            case ReturnType.ELEMENT:
                return element
            case _:
                return True

    except Exception as error:
        logger.error(small_traceback(error))
        # print(error)
        # traceback.print_stack()
        # print("=========")


def catch_err(func, *args, handle=lambda e: e, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        return handle(e)


def parse_interval(time_str: str):
    """
    Parsing time string in format xxw xxd xxh xxm
    """
    time = time_str.split(" ")
    total_seconds = 0
    time_units = {"w": 604800, "d": 86400, "h": 3600, "m": 60}
    for t in time:
        if len(t) < 2:
            continue
        try:
            value = int(t[:-1])
            unit = t[-1]
            total_seconds += value * time_units[unit]
        except (ValueError, KeyError):
            continue
    return total_seconds


def parse_datetime(datetime_str: str):
    """
    Parsing datetime string in format DD/MM HH:MM or just HH:MM
    """
    now = datetime.now(tz=timezone.utc)

    try:
        if "/" in datetime_str:  # Format z datą
            dt = datetime.strptime(f"{datetime_str} {now.year}", "%d/%m %H:%M %Y")
            dt = dt.replace(tzinfo=timezone.utc)
        else:  # Sam czas
            dt = datetime.strptime(datetime_str, "%H:%M").replace(
                year=now.year, month=now.month, day=now.day, tzinfo=timezone.utc
            )
        return dt
    except ValueError:
        return None


def timestamp(date: datetime):
    return int(date.replace(tzinfo=timezone.utc).timestamp())
