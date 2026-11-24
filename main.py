
import network
import socket

wlan = network.WLAN(network.STA_IF)

HTML = """<!DOCTYPE html>
<html>
<head>
    <title>NetSpectre</title>
</head>
<body>
    <h1>NetSpectre</h1>
    <p>ESP32-S3 is online.</p>
    <p>Network monitoring initializing...</p>
</body>
</html>
"""

server = socket.socket()
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("0.0.0.0", 80))
server.listen(2)

print("NetSpectre running at http://" + wlan.ifconfig()[0])

while True:
    client, address = server.accept()

    try:
        client.recv(1024)
        response = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/html\r\n"
            "Connection: close\r\n\r\n"
            + HTML
        )
        client.sendall(response.encode())
    finally:
        client.close()
