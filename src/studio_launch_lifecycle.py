"""Graceful ownership-scoped shutdown of the Studio process spawned by Launch.

Only a Popen instance created with Launch's private pipe token may be closed.
Never enumerate or terminate unrelated FRB Studio processes.
"""
import re
import time
import subprocess

LAUNCH_CLOSE_COMMAND = '@FRB_LAUNCH_CLOSE@'


def close_owned_studio(process, pipe_token, *, opener=open, sleeper=time.sleep,
                       max_attempts=80, retry_delay=.15, exit_timeout=10):
    """Return OK, CANCEL or ERROR: ...; never forcefully kill a process.

    The server asks its active WebView for unsaved-edit consent. Only after
    receiving OK does it schedule a normal WinForms Close().
    """
    if process is None or process.poll() is not None:
        return 'OK'
    if not isinstance(pipe_token, str) or not re.fullmatch(r'[0-9a-fA-F]{32}', pipe_token):
        return 'ERROR: Launch-owned Studio pipe token is unavailable'
    address = r'\\.\pipe\frb_studio_launch_' + pipe_token
    response = 'ERROR: Studio shutdown pipe is unavailable'
    for attempt in range(max_attempts):
        if process.poll() is not None:
            return 'OK'
        try:
            with opener(address, 'r+b', buffering=0) as channel:
                channel.write((LAUNCH_CLOSE_COMMAND + '\n').encode('utf-8'))
                raw = channel.readline()
                response = raw.decode('utf-8', errors='replace').strip() if raw else 'ERROR: Studio disconnected during shutdown'
            break
        except OSError as exc:
            response = 'ERROR: Studio shutdown pipe unavailable: ' + str(exc)
            if attempt + 1 < max_attempts:
                sleeper(retry_delay)
    if response != 'OK':
        return response
    try:
        process.wait(timeout=exit_timeout)
    except subprocess.TimeoutExpired:
        return 'ERROR: Studio did not close after confirmation'
    return 'OK'
