from __future__ import annotations
import re
from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional

_RAW_RE = re.compile(r"(?P<site>[^_]+)_BM_(?P<date>\d{8})_(?P<level>L\d{2})_(?P<file>F\d{2})\.dat$", re.IGNORECASE)
_HDR_RE = re.compile(r"(?P<site>[^_]+)_BM(?:HEADER|HEARDER)_(?P<valid_from>\d{12})_(?P<level>L\d{2})_(?P<file>F\d{2})\.csv$", re.IGNORECASE)


@dataclass(frozen=True)
class RawFileId:
    site: str
    date: date
    level: str
    file: str


@dataclass(frozen=True)
class HeaderFileId:
    site: str
    valid_from: datetime
    level: str
    file: str


def parse_raw_filename(name: str) -> Optional[RawFileId]:
    m = _RAW_RE.search(name)
    if not m:
        return None
    d = datetime.strptime(m.group("date"), "%Y%m%d").date()
    return RawFileId(site=''.join(c for c in m.group("site").upper() if c.isalnum()), date=d, level=m.group("level"), file=m.group("file"))


def parse_header_filename(name: str) -> Optional[HeaderFileId]:
    m = _HDR_RE.search(name)
    if not m:
        return None
    dt = datetime.strptime(m.group("valid_from"), "%Y%m%d%H%M")
    return HeaderFileId(site=''.join(c for c in m.group("site").upper() if c.isalnum()), valid_from=dt, level=m.group("level"), file=m.group("file"))
