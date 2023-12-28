import socket
import network
import select
import uasyncio as asyncio
from urllib.parse import unquote

html_params = """<!DOCTYPE html>
<html>
<body>

<form method="post">
  <label for="username">SSID:</label><br>
  <input type="text" id="ssid" name="ssid"><br>
  <label for="pwd">Password:</label><br>
  <input type="password" id="pwd" name="pwd"><br><br>
  <button type="submit">Save</button>
</form>

</body>
</html>"""

html_confirmation = """<!DOCTYPE html>
<html>
<body>
<p>SSID and password set. Access point is disabled.</p>

</body>
</html>"""

replace_dict = {
    "+":" ",
    "%28":"(",
    "%29":")",
    "%2A":"*",
    "%21":"!",
}

def start_ap():
    global ap, s
    ssid = 'PicoGJ'
    password = '123456789'
    ap = network.WLAN(network.AP_IF)
    ap.config(essid=ssid, password=password)
    ap.active(True)

    while ap.active() == False:
        pass
    print('Connection successful')
    print(ap.ifconfig())

    addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(10)

    print('listening on', addr)


def stop_ap():
    ap.active(False)


async def get_config_data():
    global ssid_web, pass_web

    poller = select.poll()
    poller.register(s, select.POLLIN)
    print("Configuration webserver task started...")

    while True:
        try:
            while True:
                try:
                    res = poller.poll(1)  # 1ms block
                    if res:  # Only s_sock is polled
                        cl, addr = s.accept()  # get client socket
                        print('client connected from', addr)
                        request = cl.recv(1024)

                        request = str(request)
                        break

                    else:
                        await asyncio.sleep_ms(100)
                        continue

                except OSError as e:
                    if cl:
                        cl.close()
                    print('TCP Connection closed unexpectedly')

            pos_ssid = request.find("ssid")
            if pos_ssid > 0:
                pos_end = request[pos_ssid:].find("'")
                data = request[pos_ssid:pos_ssid + pos_end]
                ssid_web, pass_web = data.replace("ssid=", "").replace("pwd=", "").split("&")
                for key, rep in replace_dict.items():
                    ssid_web = ssid_web.replace(key,rep)
                    pass_web = pass_web.replace(key,rep)
                # print(data)
                print('ssid:', ssid_web)
                print('pass:', pass_web)
                cl.send('HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n')
                cl.send(html_confirmation)
                cl.close()
                s.close()
                return ssid_web, pass_web

            cl.send('HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n')
            cl.send(html_params)
            cl.close()

        except OSError as e:
            cl.close()
            print('connection closed')

#
# # ssid, password = "Monitoring109a","vegaspalmas"
# wlan = network.WLAN(network.STA_IF)
# wlan.active(True)
# wlan.connect(ssid_web,pass_web)
# time.sleep(2)
# print(wlan.isconnected(),wlan.ifconfig())
# while True:
#     if wlan.isconnected():
#
#         time.sleep(3)
#         break
