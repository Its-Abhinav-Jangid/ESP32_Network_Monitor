import os
import time

LOG_FILE = "logs.csv"

if LOG_FILE not in os.listdir():
    with open(LOG_FILE, "w") as f:
        f.write("timestamp,ssid_visible,dns_up,gateway_up\n")

MAX_BUFFER = 30
buffer = []
last_state = None


def log_hearbeat(ssid_visible, dns_up, gateway_up):
    global last_state
    state = (ssid_visible, dns_up, gateway_up)
    # 946684800 to sync with standard timestamp format
    line = f"{time.time() + 946684800},{ssid_visible},{dns_up},{gateway_up}\n"

    buffer.append(line)

    if (last_state is not None and state != last_state) or len(buffer) >= MAX_BUFFER:
        with open(LOG_FILE, "a") as f:
            f.write("".join(buffer))
        buffer.clear()

    last_state = state
