"""Unified Railway runtime for Madmext Ads.

All feature modules are installed on the same Flask app before Gunicorn
starts serving requests. This prevents frontend/backend route drift.
"""

import os

from flask import Response, jsonify, request, send_from_directory, session

from server import app
from app import gads_campaign_rows