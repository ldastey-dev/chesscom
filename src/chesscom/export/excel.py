"""Excel report writer for the Chess.com club management tools.

Consolidates the duplicated export code from the four legacy scripts into
a single, consistently-behaved implementation backed by ``openpyxl``.

Typical usage::

    from chesscom.export.excel import ExcelReportWriter, SheetConfig

    writer = ExcelReportWriter(
        output_dir="output",
        base_name="Club Member Summary Report",
        sheets=[
            SheetConfig(
                name="Members",
                dataframe=df,
                hyperlink_column="Username",
                hyperlink_url_template="https://www.chess.com/member/{value}",
            )
        ],
    )
    path = writer.write()
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import pandas as pd
from openpyxl.styles import Font


@dataclass
class SheetConfig:
    """Configuration for a single worksheet within an Excel workbook.

    Attributes:
        name: Sheet tab name (max 31 characters; truncated silently by
            openpyxl if longer).
        dataframe: Data to write.  Written with ``index=False``.
        hyperlink_column: Optional column name whose cell values should be
            turned into hyperlinks.  Must exactly match a column in
            *dataframe*.
        hyperlink_url_template: URL pattern with a ``{value}`` placeholder
            that is replaced by each cell value.  Required when
            *hyperlink_column* is set; ignored otherwise.
    """

    name: str
    dataframe: pd.DataFrame
    hyperlink_column: str | None = field(default=None)
    hyperlink_url_template: str | None = field(default=None)


class ExcelReportWriter:
    """Write one or more DataFrames to a single ``.xlsx`` workbook.

    Handles unique filename generation to prevent overwriting previous
    outputs: if ``<base_name>.xlsx`` already exists in *output_dir* it
    appends an incrementing counter (``<base_name>_1.xlsx``,
    ``<base_name>_2.xlsx``, …).

    Args:
        output_dir: Directory in which the workbook is created.  Created
            automatically if it does not yet exist.
        base_name: Base file name, without extension.
        sheets: Ordered list of :class:`SheetConfig` objects; each becomes
            one worksheet.

    Example:
        >>> writer = ExcelReportWriter("output", "Report", [SheetConfig("Data", df)])
        >>> path = writer.write()
        >>> print(path)
        output/Report.xlsx
    """

    _HYPERLINK_FONT = Font(color="FF0000FF", underline="single")

    def __init__(
        self,
        output_dir: str,
        base_name: str,
        sheets: list[SheetConfig],
    ) -> None:
        self.output_dir = output_dir
        self.base_name = base_name
        self.sheets = sheets

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write(self) -> str:
        """Write the workbook to disk and return the absolute path.

        Creates *output_dir* if it does not exist.  Generates a unique
        filename so that previous outputs are never overwritten.

        Returns:
            Absolute path of the created ``.xlsx`` file.

        Raises:
            ValueError: When :attr:`SheetConfig.hyperlink_column` is set
                but :attr:`SheetConfig.hyperlink_url_template` is ``None``
                or empty.
        """
        self._validate()
        os.makedirs(self.output_dir, exist_ok=True)
        path = self._unique_path()

        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            for sheet in self.sheets:
                sheet.dataframe.to_excel(writer, sheet_name=sheet.name, index=False)

                if sheet.hyperlink_column:
                    self._apply_hyperlinks(writer, sheet)

        return path

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate(self) -> None:
        for sheet in self.sheets:
            if sheet.hyperlink_column and not sheet.hyperlink_url_template:
                raise ValueError(
                    f"Sheet '{sheet.name}': hyperlink_url_template is required "
                    f"when hyperlink_column is set."
                )

    def _unique_path(self) -> str:
        """Return the first non-existing ``.xlsx`` path in *output_dir*."""
        candidate = os.path.join(self.output_dir, f"{self.base_name}.xlsx")
        counter = 1
        while os.path.exists(candidate):
            candidate = os.path.join(
                self.output_dir, f"{self.base_name}_{counter}.xlsx"
            )
            counter += 1
        return candidate

    def _apply_hyperlinks(
        self, writer: pd.ExcelWriter, sheet: SheetConfig
    ) -> None:
        """Inject hyperlinks into *sheet.hyperlink_column* cells.

        Row 1 is the header; data rows start at row 2.

        Args:
            writer: The open :class:`pd.ExcelWriter` (openpyxl engine).
            sheet: Sheet configuration containing column and URL template.
        """
        df = sheet.dataframe
        if sheet.hyperlink_column not in df.columns:
            return

        worksheet = writer.sheets[sheet.name]
        col_index = df.columns.get_loc(sheet.hyperlink_column) + 1  # 1-based

        for row_offset, value in enumerate(df[sheet.hyperlink_column], start=2):
            cell = worksheet.cell(row=row_offset, column=col_index)
            cell.value = str(value)
            cell.hyperlink = sheet.hyperlink_url_template.format(value=value)
            cell.font = self._HYPERLINK_FONT
