"""Convenience entrypoint forwarding to scripts/spikes/paytm_spike.py."""

from __future__ import annotations

import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from scripts.spikes.paytm_spike import main

if __name__ == "__main__":
    raise SystemExit(main())
