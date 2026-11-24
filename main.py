
from microdot import Microdot
import network
import time
import os
import secrets
WIFI_SSID = secrets.WIFI_SSID
WIFI_PASSWORD = secrets.WIFI_PASSWORD
print(WIFI_SSID)
print(WIFI_PASSWORD)


def connect_to_wifi():
    import machine
    wlan = network.WLAN()
    wlan.active(True)
    time.sleep(2)
    if not wlan.isconnected():
        print('connecting to network...')
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        while not wlan.isconnected():
            machine.idle()
    print('network config:', wlan.ifconfig())


connect_to_wifi()


app = Microdot()


@app.route("/")
async def index(request):
    return "Hello from ESP32!"


@app.route("/api/status")
async def status(request):
    return {
        "device": "ESP32-S3",
        "status": "online"
    }


app.run(port=80)
