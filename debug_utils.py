import datetime

def debug_log(msg):
    try:
        with open("debug.log", "a") as f:
            f.write(f"{datetime.datetime.now().isoformat()} - {msg}\n")
            f.flush()
    except Exception as e:
        # Optional: print or log exception during debug
        print(f"Logging error: {e}")
