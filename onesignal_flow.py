import csv
import io
import json
import os
from datetime import datetime, timezone

import psycopg2.extras
import requests
from flask import Response, jsonify, request, session


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _ts(value):
    if value in (None, '', 0):
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    except (Type