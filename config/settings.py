"""Project-wide settings: paths and environment-based options.

Sensitive values are read from the private ".env" file, never typed
directly into source code.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# This file is ACALE_Project/config/settings.py, so two ".parent" steps
# take us up to the project root folder (ACALE_Project).
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load values from ACALE_Project/.env if the file exists.
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
SENSOR_DATA_DIR = DATA_DIR / "sensor_data"
SIMULATION_RESULTS_DIR = DATA_DIR / "simulation_results"
LOG_DIR = DATA_DIR / "logs"

RESULTS_DIR = PROJECT_ROOT / "results"
TABLES_DIR = RESULTS_DIR / "tables"
GRAPHS_DIR = RESULTS_DIR / "graphs"

REQUIRED_DIRECTORIES = [
    SENSOR_DATA_DIR,
    SIMULATION_RESULTS_DIR,
    LOG_DIR,
    TABLES_DIR,
    GRAPHS_DIR,
]

# ---------------------------------------------------------------------------
# Project identity
# ---------------------------------------------------------------------------
PROJECT_NAME = "ACALE"
PROJECT_FULL_NAME = (
    "Adaptive Context-Aware Lightweight Encryption for Secure and "
    "Energy-Efficient Data Transmission in Agricultural IoT"
)


# ---------------------------------------------------------------------------
# Environment-based options
# ---------------------------------------------------------------------------
def _read_int(name, default):
    """Read an integer from the environment; use the default if missing/invalid."""
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


ENVIRONMENT = os.getenv("ACALE_ENV", "development")
LOG_LEVEL = os.getenv("ACALE_LOG_LEVEL", "INFO").upper()
RANDOM_SEED = _read_int("ACALE_RANDOM_SEED", 42)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def ensure_directories():
    """Create the data and results folders if they do not exist yet."""
    for directory in REQUIRED_DIRECTORIES:
        directory.mkdir(parents=True, exist_ok=True)


def get_master_secret_hex():
    """Return the master secret (hex text) from .env, or "" if not set.

    SECURITY: never print or log the value returned by this function.
    It is not used in Phase 1.
    """
    return os.getenv("ACALE_MASTER_SECRET_HEX", "")