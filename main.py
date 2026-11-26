from microdot import Microdot, send_file
import network
import secrets
import socket
import struct
import os
import storage
import asyncio
import ntptime
import time
import errno
import urequests
import machine

WIFI_SSID = secrets.WIFI_SSID
WIFI_PASSWORD = secrets.WIFI_PASSWORD
print(WIFI_SSID)
print(WIFI_PASSWORD)


def reset_esp32_wifi():
    wlan = network.WLAN()
    wlan.active(False)
    time.sleep(2)
    wlan.active(True)
    time.sleep(2)


reset_esp32_wifi()


def create_AP(ssid="ESP32"):
    ap = network.WLAN(network.WLAN.IF_AP)  # create access-point interface
    ap.active(True)
    ap.config(ssid=ssid)              # set the SSID of the access point
    # set how many clients can connect to the network
    ap.config(max_clients=10)
    print("AP active SSID: ", ssid, "Ifconfig: ", ap.ifconfig())
    return ap


AP = create_AP()  # Create AP first anyway to serve dashboard immediately if wifi fails


def check_wifi_ssid_visible(ssid):
    wlan = network.WLAN()
    networks = wlan.scan()
    exists = any(net[0].decode() == ssid for net in networks)
    return exists


def connect_to_wifi():

    wlan = network.WLAN()
    wlan.active(True)
    time.sleep(2)
    if not wlan.isconnected() and check_wifi_ssid_visible(WIFI_SSID):
        print('connecting to network...')
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        while not wlan.isconnected():
            machine.idle()
    print('network config:', wlan.ifconfig())
    return wlan


wlan = connect_to_wifi()
time.sleep(5)  # to avoid immediate dns lookup errors


def check_dns_server_up():
    # AI Generated low level function to skip dns cache
    def is_hostname_resolved(hostname, dns_server=None, timeout=2.0, retries=2):
        """Returns True if hostname resolves to a valid non-zero IPv4 address, else False."""
        if dns_server is None:
            wlan = network.WLAN(network.STA_IF)
            if not wlan.isconnected():
                return False
            dns_server = wlan.ifconfig()[3]

        for _ in range(retries):
            tx_id = int.from_bytes(os.urandom(2), "big")
            query = struct.pack(">HHHHHH", tx_id, 0x0100, 1, 0, 0, 0)
            for part in hostname.strip(".").split("."):
                query += bytes([len(part)]) + part.encode("ascii")
            query += b"\x00\x00\x01\x00\x01"  # End of name, Type A, Class IN

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            try:
                sock.sendto(query, (dns_server, 53))
                resp, _ = sock.recvfrom(512)
                if len(resp) < 12:
                    continue

                r_id, flags, qdcount, ancount, _, _ = struct.unpack(
                    ">HHHHHH", resp[:12])
                if r_id != tx_id or (flags & 0x8000) == 0 or (flags & 0x000F) != 0 or ancount == 0:
                    # Server answered with error (e.g., NXDOMAIN/SERVFAIL) or no answers
                    return False

                # Skip Question section
                offset = 12
                for _ in range(qdcount):
                    while offset < len(resp) and resp[offset] != 0:
                        offset += resp[offset] + 1
                    offset += 5

                # Scan Answer section for a valid IPv4 A record (skips CNAMEs)
                for _ in range(ancount):
                    if offset >= len(resp):
                        break
                    if (resp[offset] & 0xC0) == 0xC0:
                        offset += 2
                    else:
                        while offset < len(resp) and resp[offset] != 0:
                            offset += resp[offset] + 1
                        offset += 1

                    if offset + 10 > len(resp):
                        break
                    atype, _, _, rdlength = struct.unpack(
                        ">HHIH", resp[offset:offset + 10])
                    offset += 10

                    if atype == 1 and rdlength == 4 and offset + 4 <= len(resp):
                        if resp[offset:offset + 4] != b"\x00\x00\x00\x00":
                            return True
                    offset += rdlength

                return False  # Answers existed, but none were a valid non-zero IPv4
            except OSError:
                continue  # Retry on UDP timeout or transient socket error
            finally:
                sock.close()

        return False

    return is_hostname_resolved("google.com", wlan.ifconfig()[3])


def get_wifi_signal_strength(ssid):
    wlan = network.WLAN()
    networks = wlan.scan()

    ssid = ssid.encode('utf-8')

    for net in networks:
        if net[0] == ssid:

            return net[3]

    return None


def is_gateway_up(gateway_ip, port=80, timeout=2):
    try:
        sock = socket.socket()
        sock.settimeout(2)
        sock.connect((gateway_ip, port))
        return True
    except OSError as e:
        # If router actively rejected the port that means its still up
        if e.errno == errno.ECONNREFUSED:
            return True
        return False


def raw_head_request(ip_address, host_domain):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2.0)

    try:
        s.connect((ip_address, 80))

        request = (
            f"HEAD /generate_204 HTTP/1.1\r\n"
            f"Host: {host_domain}\r\n"
            f"Connection: close\r\n\r\n"
        )
        s.send(request.encode("utf-8"))

        response_line = s.readline()
        if not response_line:
            return {"error": "Empty response", "status_code": None}

        parts = response_line.decode("utf-8").split(" ")
        status_code = int(parts[1]) if len(parts) >= 2 else None

        return {"error": None, "status_code": status_code}

    except Exception as e:
        return {"error": e, "status_code": None}

    finally:
        s.close()


def fetch_website(url):
    response = None
    try:
        response = urequests.head(url, timeout=1.5)

        status_code = response.status_code
        return {"error": None, "status_code": status_code}
    except OSError as e:
        # Catches Wi-Fi drops, DNS failures (-202), timeouts (ETIMEDOUT), and out-of-memory (ENOMEM)
        print("Network or socket error:", e)
        return {"error": e}
    finally:
        if response is not None:
            response.close()


def sync_time():
    try:
        ntptime.settime()
        print("Time synced:", time.localtime())
        return True
    except Exception as e:
        print("NTP sync failed:", e)
        return False


WEBSITE_IP = None
try:
    WEBSITE_IP = socket.getaddrinfo("clients3.google.com", 80)[0][-1][0]
except OSError as e:
    print(f"Failed to get website ip, error: {e}")
    WEBSITE_IP = "216.239.35.0"

sync_time()
app = Microdot()


@app.route("/")
async def index(request):
    return send_file("frontend/home.html")


@app.route('/static/<path:path>')
async def static_files(request, path):
    # Prevent directory traversal attack
    if '..' in path:
        return 'Not found', 404
    return send_file('frontend/static/' + path)


@app.route("/api/status")
async def status(request):
    return get_wifi_status()


@app.route("/api/debug/save_buffer_logs_to_flash")
async def save_buffer_logs_to_flash(request):
    storage.log_hearbeat(ssid_visible=None, dns_up=None, gateway_up=None,
                         internet_up=None, status_code=None, only_save_buffer_to_flash=True)
    return "Saved!"


@app.route("/api/logs")
async def logs(request):
    return storage.get_logs()


def get_wifi_status():

    global wlan
    if not wlan.isconnected():  # if not connected, early return
        return {
            "dns_up": False,
            "internet_up": False,
            "ssid_visible": False,
            "ssid_name": "N/A",
            "gateway_up": False,
            "dns_server": None,
            "gateway_ip": None,
            "signal_strength":  None
        }
    response = {
        "dns_up": check_dns_server_up(),
        "ssid_name": WIFI_SSID,
        "ssid_visible": wlan.isconnected(),
        "gateway_up": is_gateway_up(wlan.ifconfig()[2], 80),
        "dns_server": wlan.ifconfig()[3],
        "gateway_ip": wlan.ifconfig()[2],
        "signal_strength": wlan.status('rssi') if wlan.isconnected() else None
    }

    website_response = raw_head_request(WEBSITE_IP, "google.com")
    if (not website_response["error"]):
        response["internet_up"] = True
        response["status_code"] = website_response["status_code"]

    else:
        response["internet_up"] = False
        response["status_code"] = None

    return response


async def monitor_loop():
    global WEBSITE_IP
    global wlan
    while True:
        status = get_wifi_status()
        all_ok = (status["ssid_visible"] and status["gateway_up"]
                  and status["dns_up"] and status["internet_up"])

        if not status["ssid_visible"] and check_wifi_ssid_visible(WIFI_SSID):
            wlan.connect(WIFI_SSID, WIFI_PASSWORD)
            aysncio.sleep(2)
            try:
                WEBSITE_IP = socket.getaddrinfo(
                    "clients3.google.com", 80)[0][-1][0]
            except OSError as e:
                print(f"Failed to get website ip, error: {e}")
                WEBSITE_IP = "216.239.35.0"

            sync_time()

        storage.log_hearbeat(
            ssid_visible=status["ssid_visible"], dns_up=status["dns_up"], gateway_up=status["gateway_up"], internet_up=status["internet_up"], status_code=status["status_code"])
        await asyncio.sleep(30)


async def main():
    asyncio.create_task(monitor_loop())
    await app.run(port=80)
asyncio.run(main())
