import os
from flask import jsonify, send_from_directory, session, request, Response
from server import app
import meta_sync_flow
import onesignal_flow
from app import get_db, read_logs, write_logs, require_admin


meta_sync_flow.install(
    app,
    get_db=get_db,
    read_logs=read_logs,
    write_logs=write_logs,
)

onesignal_flow.install(
    app,
    get_db=get_db,
    require_admin=require_admin,
)


def _panel_html():
    path = os.path.join('.', 'index.html')
    with