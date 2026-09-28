"""Practice report (F-08): per-bar findings against expert references, as HTML + JSON.

* :func:`build_report` (``pianolens.report.build``): the report data from aligned performances.
* :func:`render_html` (``pianolens.report.render``): the self-contained HTML page.
* :func:`report_from_files` / :func:`write_report` (``pianolens.report.io``): files in, files
  out. CLI: ``scripts/pianolens_report.py``.
"""

from pianolens.report.build import (
    SCHEMA,
    ReportConfig,
    ReportInputs,
    build_report,
    collect_issues,
    to_jsonable,
)
from pianolens.report.io import report_from_files, write_report
from pianolens.report.render import render_html

__all__ = [
    "SCHEMA",
    "ReportConfig",
    "ReportInputs",
    "build_report",
    "collect_issues",
    "render_html",
    "report_from_files",
    "to_jsonable",
    "write_report",
]
