import datetime

def debug_log(msg, log_file="debug.log", print_console=False):
    try:
        log_entry = f"{datetime.datetime.now().isoformat()} - {msg}\n"
        with open(log_file, "a") as f:
            f.write(log_entry)
            f.flush()
        if print_console:
            print(log_entry.strip())
    except Exception as e:
        print(f"Debug log error: {e}")
