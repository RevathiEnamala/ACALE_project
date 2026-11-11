# ACALE – Adaptive Context-Aware Lightweight Encryption

Secure and energy-efficient data transmission simulation for Agricultural IoT.

Final-year B.Tech Computer Science project.

## What this project does

ACALE simulates agricultural IoT edge sensor devices that send data to a fog
node. The system adapts its communication behaviour (for example, batching)
to sensor conditions and remaining battery energy, while the security level
stays strong at all times.

This is a **software simulation only**. No real hardware is used.

## Tech stack

- Python 3.11
- cryptography (ChaCha20-Poly1305 AEAD, HKDF-SHA256)
- numpy, pandas, matplotlib, plotly
- Streamlit (dashboard)
- pytest (testing)

## Project status

- [x] Phase 1: Environment and project structure
- [ ] Later phases: sensors, classification, key management, encryption,
      energy-aware batching, fog verification, replay detection,
      evaluation, dashboard

## Setup (Windows PowerShell)

Run from the project root (the `ACALE_Project` folder):

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Copy the settings template:

```powershell
Copy-Item .env.example .env
```

## Run

```powershell
python main.py
```

## Test

```powershell
python -m pytest -v
```

## Folder overview

- `config/` – settings and tunable parameters
- `src/acale/` – application code (edge, fog, simulation, dashboard, utils)
- `data/` – generated data and logs (not committed)
- `results/` – final tables and graphs
- `tests/` – automated tests

## Security rules followed

- No homemade cryptography or homemade MAC.
- Standard authenticated encryption from the `cryptography` library.
- Keys are derived with HKDF-SHA256 and are never logged.
- Secrets live in `.env`, which is never committed to Git.
- Battery optimisation never weakens encryption security.