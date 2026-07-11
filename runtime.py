"""Unified Railway runtime for Madmext Ads.

All optional feature modules are installed on the same Flask app before
Gunicorn starts serving requests. This avoids frontend/backend version drift.
"""

from server import app
from app import get_db, read_logs, write_logs, require_admin

import meta_sync_flow
import onesignal_flow


meta_sync_flow.install(
    app,
    get_db=get_db,
    read_logs=read_logs,
    write_logs=write_logs,
)

