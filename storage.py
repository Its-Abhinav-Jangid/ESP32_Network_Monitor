import json
import os
import time

LOG_FILE = "logs.csv"

if LOG_FILE not in os.listdir():
    with open(LOG_FILE, "w") as f:
        f.write("timestamp,ssid_visible,dns_up,gateway_up,internet_up,status_code\n")

MAX_BUFFER = 30
buffer = []
last_state = None


def buffer_to_json():
    csv = "timestamp,ssid_visible,dns_up,gateway_up,internet_up,status_code\n"
    csv += "".join(buffer)
    return csv_text_to_json(csv)


def csv_text_to_json(csv_text):
    lines = [line.strip()
             for line in csv_text.strip().split('\n') if line.strip()]
    if not lines:
        return '[]'

    headers = lines[0].split(',')
    result = []

    for line in lines[1:]:
        values = line.split(',')
        row = dict(zip(headers, values))
        result.append(row)

    return result


def get_logs():
    yield "["
    first = True
    headers = None

    with open(LOG_FILE, "r") as f:
        header_line = f.readline().strip()
        if header_line:
            headers = header_line.split(",")

        if headers:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = dict(zip(headers, line.split(",")))
                yield ("" if first else ",") + json.dumps(row)
                first = False

    if headers:
        for line in list(buffer):
            line = line.strip()
            if not line:
                continue
            row = dict(zip(headers, line.split(",")))
            yield ("" if first else ",") + json.dumps(row)
            first = False

    yield "]"


def log_hearbeat(ssid_visible, dns_up, gateway_up, internet_up, status_code, only_save_buffer_to_flash=False):
    if only_save_buffer_to_flash:
        with open(LOG_FILE, "a") as f:
            f.write("".join(buffer))
            buffer.clear()
        return True

    global last_state
    state = (ssid_visible, dns_up, gateway_up, internet_up, status_code)
    # 946684800 to sync with standard timestamp format
    line = f"{time.time() + 946684800},{ssid_visible},{dns_up},{gateway_up},{internet_up},{status_code}\n"

    buffer.append(line)

    if (last_state is not None and state != last_state) or len(buffer) >= MAX_BUFFER:
        with open(LOG_FILE, "a") as f:
            f.write("".join(buffer))
        buffer.clear()

    last_state = state
