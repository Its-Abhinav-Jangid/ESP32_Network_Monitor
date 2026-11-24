import os
import time
LOG_FILE = "logs.csv"

if LOG_FILE not in os.listdir():
    with open(LOG_FILE, "w") as f:
        f.write("timestamp,ssid_visible,dns_up,gateway_up\n")


def log_hearbeat(ssid_visible, dns_up, gateway_up):
    # 946684800 to sync with standard timestamp format
    line = f"{time.time() + 946684800},{ssid_visible},{dns_up},{gateway_up}\n"
    with open(LOG_FILE, "a") as f:
        f.write(line)
