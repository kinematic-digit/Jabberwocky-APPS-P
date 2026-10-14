#=-----------------------------------------------------------------------------
# JWS V3.0 SYSTEM PRESENTATION LOGGING INTERFACE (jws_reporter.py)
#=-----------------------------------------------------------------------------
#!/usr/bin/env python3
"""Jabberwocky Scrubber (JWS v3.0) High-Visibility Presentation Interface.

Implements the text buffering matrix. Programmatically mirrors high-visibility 
summary logs at both the absolute top and bottom layers of the output text data
to achieve zero-scroll terminal accessibility in browser dashboard interfaces.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

class Reporter:
    """Manages internal log buffering, terminal text wrapping, and mirrored dashboard outputs."""
    def __init__(self, output_path: Path | None = None, no_file: bool = False, max_width: int = 80):
        self.lines: list[str] = []
        self.output_path = output_path
        self.no_file = no_file
        self.max_width = max_width

    def echo(self, text: str = "") -> None:
        """Appends a line or recursively text-wraps long configuration descriptions safely."""
        if not text:
            self.lines.append("")
            return

        for raw_line in text.splitlines():
            if len(raw_line) > self.max_width and not any(raw_line.startswith(c) for c in ["├", "└", "│"]):
                wrapped = textwrap.fill(raw_line, width=self.max_width, subsequent_indent="  ")
                self.lines.extend(wrapped.splitlines())
            else:
                self.lines.append(raw_line)

    def section(self, title: str, note: str | None = None) -> None:
        """Generates standard divided headers separating discrete validation phases."""
        self.echo()
        self.echo(f"=== {title.upper()} ===")
        self.echo("-" * min(len(title) + 8, self.max_width))
        if note:
            self.echo(f"  ℹ️ {note}")

    def append_mirrored_dashboards(self, score_label: str, summary_points: list[str]) -> None:
        """Splices matching visual indicator blocks to the top and bottom of the buffer stream."""
        dashboard_block = [
            "",
            "================================================================================",
            f" 📋 JWS v3.0 OPERATION DASHBOARD SUMMARY: {score_label}",
            "================================================================================",
        ]
        for pt in summary_points:
            dashboard_block.append(f"  • {pt}")
        dashboard_block.append("================================================================================")
        dashboard_block.append("")

        # Inject into the absolute top layer (index 0) and append to the absolute bottom layer
        self.lines = dashboard_block + self.lines + dashboard_block

    def flush_to_stdout(self) -> None:
        """Outputs the full combined string buffer to the console stream in a single pass."""
        if self.lines:
            print("\n".join(self.lines))

    def write_to_disk(self) -> None:
        """Writes the structured array out to jws_hygiene_report.txt if active."""
        if self.no_file or self.output_path is None:
            return
        try:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            self.output_path.write_text("\n".join(self.lines) + "\n", encoding="utf-8")
        except OSError:
            pass
