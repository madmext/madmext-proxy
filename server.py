from app import app, get_db, hash_pw, read_logs, write_logs
import password_reset_flow

password_reset_flow.install(
    app,
    get_db=get_db,
    hash_pw=hash_pw,
    read_logs=read_logs,
    write_logs=write_logs
)
