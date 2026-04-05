from __future__ import annotations

import sys
from pathlib import Path


def write_output(content: str, output_path: Path | None = None) -> None:
    if output_path is None:
        print(content)
    else:
        output_path.write_text(content, encoding="utf-8")
