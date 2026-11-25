from microdot import Microdot
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


def check_wifi_ssid_visible(ssid):
    wlan = network.WLAN()
    networks = wlan.scan()
    exists = any(net[0].decode() == ssid for net in networks)
    return exists


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


def fetch_website(url):
    response = None
    try:
        response = urequests.get(url, timeout=5)
        print(response)

        status_code = response.status_code
        return {"error": None, "status_code": status_code}
    except OSError as e:
        # Catches Wi-Fi drops, DNS failures (-202), timeouts (ETIMEDOUT), and out-of-memory (ENOMEM)
        print("Network or socket error:", e)
        return {"error": e}
    finally:
        if response is not None:
            response.close()


def create_AP(ssid="ESP32"):
    ap = network.WLAN(network.WLAN.IF_AP)  # create access-point interface
    ap.active(True)
    ap.config(ssid=ssid)              # set the SSID of the access point
    # set how many clients can connect to the network
    ap.config(max_clients=10)
    print("AP active SSID: ", ssid, "Ifconfig: ", ap.ifconfig())


create_AP()


def connect_to_wifi():
    import machine
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


print(fetch_website("https://google.com"))


def sync_time():
    try:
        ntptime.settime()
        print("Time synced:", time.localtime())
        return True
    except Exception as e:
        print("NTP sync failed:", e)
        return False


sync_time()
app = Microdot()


@app.route("/")
async def index(request):
    return "Hello from ESP32!"


@app.route("/api/status")
async def status(request):
    return get_wifi_status()


def get_wifi_status():
    response = {
        "dns_up": check_dns_server_up(),
        "ssid_visible": check_wifi_ssid_visible(WIFI_SSID),
        "gateway_up": is_gateway_up(wlan.ifconfig()[2], 80)
    }
    website_response = fetch_website("https://google.com")
    if (not website_response["error"]):
        response["internet"] = {
            "up": True, "status_code": website_response["status_code"]}
    else:
        response["internet"] = {"up": False, "status_code": None}

    return response


async def monitor_loop():
    while True:
        status = get_wifi_status()
        storage.log_hearbeat(
            ssid_visible=status["ssid_visible"], dns_up=status["dns_up"], gateway_up=status["gateway_up"])
        await asyncio.sleep(30)


async def main():
    asyncio.create_task(monitor_loop())
    await app.run(port=80)
asyncio.run(main())
