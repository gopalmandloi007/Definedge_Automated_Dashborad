import datetime

def debug_log(message):
    with open("debug.log", "a") as f:
        f.write(f"{datetime.datetime.now().isoformat()} - {message}\n")
