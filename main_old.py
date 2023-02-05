import time
from machine import Pin
import network
import socket

led = Pin("LED", Pin.OUT)

wlan = network.WLAN(network.STA_IF)
wlan.active(True)

ssid, password = "Monitoring109a","vegaspalmas"
wlan.connect(ssid,password)

max_wait = 100

while max_wait > 0:
    status = wlan.status()
    if status <= 3 or status < 0:
        break
    max_wait -= 1
    print('waiting for wi-fi')
    time.sleep(4)

print("Connected to wi-fi")
for i in range(5):
    led.high()
    time.sleep(0.05)
    led.low()
    time.sleep(0.05)
    
    
# For demo purposes, we have an infinite loop here
# while True:
#     led.high()
#     time.sleep(0.5)
#     led.low()
#     time.sleep(0.5)
   
   
#Socket
s = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
s.connect(("192.168.1.12",8500))

cnt = 0

for i in range(30):
    msg = f"testing msg {cnt}\n"
    # msg = "testos\n"
    s.send(msg)
    cnt += 1
    time.sleep(5)


