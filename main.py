
from microdot import Microdot
import network
import time
import secrets

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


def check_wifi_ssid_visible(ssid):
    wlan = network.WLAN()
    networks = wlan.scan()
    exists = any(net[0].decode() == ssid for net in networks)
    return exists


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


app = Microdot()


@app.route("/")
async def index(request):
    return "Hello from ESP32!"


@app.route("/api/status")
async def status(request):
    return {
        "ssid_visible": check_wifi_ssid_visible(WIFI_SSID),
    }


app.run(port=80)
