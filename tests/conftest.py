import os

# Avoid writing `.spn_dc_state.json` during tests when the session is exercised via the default session.
os.environ.setdefault("SPN_DC_NO_PERSIST", "1")
