
"""Launch the ACALE Phase 8 Streamlit dashboard."""

from pathlib import Path
import subprocess
import sys


def main():
    project_root = Path(__file__).resolve().parent

    dashboard_app = (
        project_root
        / "src"
        / "acale"
        / "dashboard"
        / "app.py"
    )

    if not dashboard_app.exists():
        raise SystemExit(
            f"Dashboard app not found: {dashboard_app}"
        )

    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(dashboard_app),
    ]

    raise SystemExit(
        subprocess.call(command)
    )


if __name__ == "__main__":
    main()
