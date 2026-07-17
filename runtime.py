"""Unified Railway runtime for Madmext Ads.

All feature modules are installed on the same Flask app before Gunicorn
starts serving requests. This prevents frontend/backend route drift.
"""

import os

import psycopg2.extras
from flask import Response, jsonify, request, send_from_directory, session

from server import app
from app import gads_campaign_rows, get_db, get_ga4_token, get_users, hash_pw, read_logs, require_admin, save_users, verify_pw, write_logs

import clarity_flow
import meta