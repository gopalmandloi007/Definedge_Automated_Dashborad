import datetime

def debug_log(message):
    """Write a log message with a timestamp to debug.log (append mode)."""
    try:
        with open("debug.log", "a") as f:
            f.write(f"{datetime.datetime.now().isoformat()} - {message}\n")
    except Exception as e:
        # If logging fails, print to stderr for emergency debug
        import sys
        print(f"DEBUG LOG FAILED: {e} | Original message: {message}", file=sys.stderr)
