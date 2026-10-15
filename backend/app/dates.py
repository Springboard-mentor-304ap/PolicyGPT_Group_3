from datetime import date, datetime, timezone


def utc_today() -> date:
    """Today's calendar date in UTC.

    Deadline cutoffs must use one timezone everywhere: the host-local
    ``date.today()`` shifts the boundary by up to a day depending on the
    server's TZ setting.
    """

    return datetime.now(timezone.utc).date()
