"""Tunable simulation parameters for ACALE.

Change numbers HERE instead of scattering them through the code.
These are normal configuration values, NOT secrets.

Important design rule: battery and context settings may change HOW OFTEN
data is sent (batching), but they must NEVER weaken the encryption.
"""

# ---------------------------------------------------------------------------
# Simulation size and timing
# ---------------------------------------------------------------------------
NUM_EDGE_DEVICES = 5            # number of simulated sensor devices
NUM_FOG_NODES = 1               # number of simulated fog nodes
SIMULATION_STEPS = 500          # how many time steps one run lasts
SAMPLING_INTERVAL_SECONDS = 60  # time between sensor readings

# ---------------------------------------------------------------------------
# Sensor value ranges (min, max) used for realistic sensor simulation
# ---------------------------------------------------------------------------
SENSOR_RANGES = {
    "soil_moisture_percent": (5.0, 60.0),
    "temperature_celsius": (5.0, 50.0),
    "humidity_percent": (20.0, 100.0),
}

# ---------------------------------------------------------------------------
# Context thresholds (used by the classifier in a later phase)
# ---------------------------------------------------------------------------
SOIL_MOISTURE_CRITICAL_LOW = 15.0   # below this: urgent irrigation need
TEMPERATURE_CRITICAL_HIGH = 40.0    # above this: heat stress
TEMPERATURE_CRITICAL_LOW = 5.0      # below this: frost risk
HUMIDITY_CRITICAL_HIGH = 90.0       # above this: disease risk

# ---------------------------------------------------------------------------
# Battery and energy model
# ---------------------------------------------------------------------------
BATTERY_CAPACITY_JOULES = 10000.0   # starting energy of each device
BATTERY_LOW_PERCENT = 30.0          # below this: save energy by batching
BATTERY_CRITICAL_PERCENT = 10.0     # below this: strongest batching

# ---------------------------------------------------------------------------
# Batching (how many readings are sent together in one frame)
# ---------------------------------------------------------------------------
BATCH_SIZE_URGENT = 1       # urgent data is sent immediately
BATCH_SIZE_NORMAL = 3
BATCH_SIZE_LOW_BATTERY = 6
BATCH_SIZE_MAX = 10

# ---------------------------------------------------------------------------
# Security constants (fixed by the standards, not tunable shortcuts)
# ---------------------------------------------------------------------------
AEAD_ALGORITHM = "ChaCha20-Poly1305"
KEY_SIZE_BYTES = 32          # 256-bit key
NONCE_SIZE_BYTES = 12        # 96-bit nonce required by ChaCha20-Poly1305
TAG_SIZE_BYTES = 16          # 128-bit authentication tag
HKDF_HASH = "SHA256"
KEY_ROTATION_INTERVAL_FRAMES = 100   # new epoch key after this many frames
REPLAY_WINDOW_SIZE = 64              # how many recent counters the fog remembers


def validate_parameters():
    """Check that the parameters make sense. Returns a list of problem messages.

    An empty list means everything looks fine.
    """
    problems = []

    if NUM_EDGE_DEVICES < 1:
        problems.append("NUM_EDGE_DEVICES must be at least 1.")
    if NUM_FOG_NODES < 1:
        problems.append("NUM_FOG_NODES must be at least 1.")
    if SIMULATION_STEPS < 1:
        problems.append("SIMULATION_STEPS must be at least 1.")
    if not (0 < BATTERY_CRITICAL_PERCENT < BATTERY_LOW_PERCENT < 100):
        problems.append(
            "Battery thresholds must satisfy 0 < CRITICAL < LOW < 100."
        )
    if not (1 <= BATCH_SIZE_URGENT <= BATCH_SIZE_NORMAL
            <= BATCH_SIZE_LOW_BATTERY <= BATCH_SIZE_MAX):
        problems.append("Batch sizes must increase from URGENT up to MAX.")
    if KEY_SIZE_BYTES != 32:
        problems.append("KEY_SIZE_BYTES must be 32 for ChaCha20-Poly1305.")
    if NONCE_SIZE_BYTES != 12:
        problems.append("NONCE_SIZE_BYTES must be 12 for ChaCha20-Poly1305.")
    if TAG_SIZE_BYTES != 16:
        problems.append("TAG_SIZE_BYTES must be 16 (128-bit tag).")
    if KEY_ROTATION_INTERVAL_FRAMES < 1:
        problems.append("KEY_ROTATION_INTERVAL_FRAMES must be at least 1.")
    if REPLAY_WINDOW_SIZE < 1:
        problems.append("REPLAY_WINDOW_SIZE must be at least 1.")

    for sensor_name, (low, high) in SENSOR_RANGES.items():
        if low >= high:
            problems.append(f"Sensor range for {sensor_name} must have min < max.")

    return problems