import datetime

def debug_log(msg):
    try:
        with open("debug.log", "a") as f:
            f.write(f"{datetime.datetime.now().isoformat()} - {msg}\n")
    except Exception:
        pass
