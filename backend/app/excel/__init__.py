"""Excel katmanı — metraj şablonu, okuyucu ve domain köprüsü.

Paket, :mod:`app.domain` gibi HTTP'den bağımsızdır; FastAPI bu aşamada devrede
değildir. Şablon ve okuyucu aynı kolon adlarını :mod:`app.excel.models` içinden
okur, böylece ikisinin ayrışması mümkün değildir.
"""

from app.excel.bridge import (
    MetrajBatch,
    MetrajSourceRow,
    RejectedMetrajRow,
    to_domain,
)
from app.excel.models import (
    GUIDE_SHEET_NAME,
    OPTIONAL_COLUMNS,
    REQUIRED_COLUMNS,
    TEMPLATE_SHEET_NAME,
    CellIssue,
    MetrajColumn,
    MetrajReadResult,
    MetrajRow,
    ScopeIssue,
)
from app.excel.numbers import (
    NumberParseError,
    decimal_from_number,
    parse_decimal_text,
    parse_percent_text,
)
from app.excel.reader import (
    MetrajFileError,
    MetrajFileErrorCode,
    header_key,
    read_metraj,
)
from app.excel.template import (
    TEMPLATE_COLUMNS,
    TEMPLATE_EXAMPLE_ROWS,
    TemplateExampleRow,
    build_metraj_template,
    template_headers,
)

__all__ = [
    "GUIDE_SHEET_NAME",
    "OPTIONAL_COLUMNS",
    "REQUIRED_COLUMNS",
    "TEMPLATE_COLUMNS",
    "TEMPLATE_EXAMPLE_ROWS",
    "TEMPLATE_SHEET_NAME",
    "CellIssue",
    "MetrajBatch",
    "MetrajColumn",
    "MetrajFileError",
    "MetrajFileErrorCode",
    "MetrajReadResult",
    "MetrajRow",
    "MetrajSourceRow",
    "NumberParseError",
    "RejectedMetrajRow",
    "ScopeIssue",
    "TemplateExampleRow",
    "build_metraj_template",
    "decimal_from_number",
    "header_key",
    "parse_decimal_text",
    "parse_percent_text",
    "read_metraj",
    "template_headers",
    "to_domain",
]
