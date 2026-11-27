# ESP32 Network Monitor

First, a huge thanks to phantom hackatime for letting me rediscover the joy of coding after a long time ❤️.
The project was a great a experience of learning, building and optimizing.

# Introduction

The project aims to monitor your home wifi for downtimes by keeping logs of the uptime of wifi, dns resolution, gateway accessibility and internet reachability with a embedded harware device like the esp32. There's also an option to check reachability for a pariticular url and find what's wrong.

# Features

- Neon-themed dashboard served over the home wifi and the esp's own network which includes realtime status of your home network and earlier uptime logs.
- The esp logs ssid visibility, dns resolution, gateway and internet reachability every 30s
- Url diagnostics section lets you check the reachability of a pariticular website and find out what's failing.
- View logs history of uptime of your home network
- Persistent storage of logs in the board's flash
- Logs are buffered in memory before writing to flash and saved in bulk to prevent flash from wearing out.
- Mobile-first responsive ui

# Screenshot(s)

![Initial design]("images/first_design.png")

_wait, its just one~_

# How to run

Although I made the project with an esp32 s3, I think it can run in any board which:

- Support micropython.
- Have wifi connectivity.
- Provide the networking functionality and APIs required by the project.

However **the project has only been tested on an ESP 32 S3**

To run this on your own board:

- Flash it with micropython [Micropython website](https://micropython.org/download/) according to your board with your preferred method, I used [Thonny]("https://thonny.org/") with this [youtube tutorial]("https://www.youtube.com/watch?v=qoogOzSM0cM")

- Create your secrets.py file in this format:

```python
# All entries are case-sensitive
WIFI_SSID = "YOUR_WIFI_SSID"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"
```

- Upload the code to the board using your preferred method, I used Micropico for this.
- Run the main.py in the board to start the server, you will see something like this on the serial console:

```bash
AP active SSID:  ESP32
Ifconfig:  ('192.168.4.1', '255.255.255.0', '192.168.4.1', '0.0.0.0')
connecting to network...
network config: ('192.168.1.33', '255.255.255.0', '192.168.1.1', '192.168.1.1')

```

- To visit the dashboard, connect to the esp 32 wifi and open 192.168.4.1
  OR
- Connect your home wifi which you entered in the secrets.py and open the ip address in browser shown at first in

```bash
network config: ('192.168.1.33', '255.255.255.0', '192.168.1.1', '192.168.1.1')
```

For ex, here it is **192.168.1.33**, it may differ in your case.

_Enjoy_

# Devlogs

_These are the memorable experiences from this project for me_

1. Optimize the wifi status checking to drop response time from **~8s to < 800ms**

After completing the core functionality, I observed that the dashboard seemed a bit slow, when i checked the devtools, I realised that the request for checking wifi status was taking ~8s to answer and the request was repeated every 5s, so.... yeah it got overloaded.
To fix it I made the following changes:

- Earlier to check for signal strength, it scanned all available networks, searched for our own network and then reported the signal strength... but you could already knew the singal strength because the esp is already connected to our home network, so I replaced that with a inbuilt function for getting signal strength of the connected network.

- Earlier, to check for internet reachability, it made a get request to google.com which obviously took a long time to resolve the dns, download the content and report back. So i replaced it with a pre fetched dns for clients3.google.com and raw socket HEAD request to /generate_204 which skipped dns resolution and downloading content, so it was much faster.

- To check for ssid visibility, earlier it scanned all networks and reported true if our home wifi was present in that list but if the esp is already connected to your home network it means the ssid is visible, so replaced that with a simple is_connected check.

After all this, the avg response time dropped from ~8s to < 800ms which seems pretty good.

2. **Redesigning the UI 2 times**
   At first I thought of a green hacker terminal-like look, so I made it in Canva and it looked decent to me only until I implemented it in code and saw it second-time, it seemed a bit too much green to me. I knew I had to make better design.

The initial design looked like this:

![Initial design]("images/first_design.png")
Tbh, now it looks good to me for some reason...

So, I went to colorhunts to look for a color pallete, and I found a neon style color pallete, so I made this:

![Second design]("images/second_design.png")

This also looked decent, but I wanted to get rid of the cards and a new layout... (idk why)
Finally I settled on this:

![Final design]("images/Home.png")
I got inspiration for this from a earlier hackathon event's website... and, it looks pretty _damn good_ to me, _doesn't it?_.

_I can yap here all day, so I'm gonna stop here..._

# Dependencies Used

- Micropython for firmware
- Microdot for webserver
- TUI css for loading spinners

_Thanks to all the wonderful people who made these programs which made this project possible_

_Made with ❤️ by Its-Abhinav-Jangid_
