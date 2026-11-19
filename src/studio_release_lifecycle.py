"""Opt out a verified Launch-owned Studio session without closing documents.

The C# NativeShell responds to @FRB_LAUNCH_RELEASE@ and keeps running after
Launch exits. The release token must come from the original child launch.
Never release or terminate an unrelated Studio process.
"""
import re
import time

RELEASE_COMMAND = '@FRB_LAUNCH_RELEASE@'


def release_owned_studio(process, pipe_token, *, opener=open, sleeper=time.sleep,
                         max_attempts=24, retry_delay=0.15):
    if process is None or process.poll() is not None:
        return 'OK'
    if not isinstance(pipe_token, str) or not re.fullmatch(r'[a-f0-9]{32}',pipe_token,re.I):
        return 'ERROR: Launch-owned Studio pipe token is unavailable'
    address = r'\\.\pipe\frb_studio_launch_' + pipe_token
    reply = 'ERROR: Studio release pipe not available'
    for attempt in range(max_attempts):
        try:
            with opener(address, 'r+b', buffering=0) as channel:
                channel.write((RELEASE_COMMAND + '\n').encode('utf-8'))
                raw = channel.readline()
                reply = raw.decode('utf-8', errors='replace').strip() if raw else 'ERROR: Studio reply missing'
            break
        except OSError as exc:
            reply = 'ERROR: Studio release pipe: ' + str(exc)
            if attempt + 1 < max_attempts:
                sleeper(retry_delay)
    return reply
