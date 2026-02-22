"""Abstract base class for all Chess.com club reports.

All concrete reports inherit from :class:`BaseReport`.  Callers invoke
:meth:`BaseReport.run` which orchestrates the three-step pipeline:

1. :meth:`collect_data` — fetch and transform data via
   :class:`~chesscom.api.client.ChessComClient`.
2. :meth:`build_sheet_configs` — map the data to one or more
   :class:`~chesscom.export.excel.SheetConfig` objects.
3. :class:`~chesscom.export.excel.ExcelReportWriter` — write the workbook
   and return the path.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from chesscom.api.client import ChessComClient
from chesscom.config import AppConfig
from chesscom.export.excel import ExcelReportWriter, SheetConfig

_CHESSCOM_PROFILE_URL = "https://www.chess.com/member/{value}"


class BaseReport(ABC):
    """Common scaffold for every report type.

    Subclasses must implement :meth:`collect_data` and
    :meth:`get_report_name`.  :meth:`build_sheet_configs` has a sensible
    default (one sheet, username-hyperlinked) that can be overridden for
    multi-sheet reports.

    Args:
        client: Configured Chess.com API client.
        config: Validated application configuration.
    """

    def __init__(self, client: ChessComClient, config: AppConfig) -> None:
        self.client = client
        self.config = config

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def collect_data(self) -> list[dict]:
        """Fetch and transform data into a list of row dicts.

        Each dict represents one row in the primary sheet.

        Returns:
            Non-empty list of row dicts suitable for ``pd.DataFrame``.
        """

    @abstractmethod
    def get_report_name(self) -> str:
        """Return the human-readable base name used for the output file.

        The name is also used as the default sheet name (truncated to 31
        characters by openpyxl if necessary).

        Returns:
            Base filename (without extension or path).
        """

    # ------------------------------------------------------------------
    # Overridable hook
    # ------------------------------------------------------------------

    def build_sheet_configs(self, data: list[dict]) -> list[SheetConfig]:
        """Map collected data to one or more worksheet configurations.

        The default implementation creates a single sheet whose name is the
        report name (truncated to 31 chars) with ``Username`` hyperlinks
        pointing to Chess.com member profiles.

        Override this method for reports that need multiple sheets or
        different hyperlink columns.

        Args:
            data: Row dicts returned by :meth:`collect_data`.

        Returns:
            List of :class:`~chesscom.export.excel.SheetConfig` instances.
        """
        sheet_name = self.get_report_name()[:31]
        df = pd.DataFrame(data)
        hyperlink_col = "Username" if "Username" in df.columns else None
        return [
            SheetConfig(
                name=sheet_name,
                dataframe=df,
                hyperlink_column=hyperlink_col,
                hyperlink_url_template=(
                    _CHESSCOM_PROFILE_URL if hyperlink_col else None
                ),
            )
        ]

    # ------------------------------------------------------------------
    # Concrete run method
    # ------------------------------------------------------------------

    def run(self) -> str:
        """Execute the full report pipeline and return the output path.

        Calls :meth:`collect_data`, builds sheet configurations via
        :meth:`build_sheet_configs`, then writes the workbook.

        Returns:
            Absolute path of the created ``.xlsx`` file.
        """
        data = self.collect_data()
        writer = ExcelReportWriter(
            output_dir="output",
            base_name=self.get_report_name(),
            sheets=self.build_sheet_configs(data),
        )
        return writer.write()
