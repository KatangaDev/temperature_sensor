import time

import machine
from machine import Pin
import network
import socket
from machine import I2C
import mcp9808
import struct


led = Pin("LED", Pin.OUT)

ssid, password = "Monitoring109a","vegaspalmas"
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
s:socket.Socket
cnt = 0

#rtc = machine.RTC()
#rtc.datetime((2023, 1, 31, 1, 20, 9, 0, 0))
# print(rtc.datetime())

with open("settings.txt","a") as f:
    f.write("file read\n")
    f.flush()

with open("settings.txt","r") as f:
    for line in f:
        print(line)


def blink(period_on=0.1, period_off=0.3, repetitions=1):
    for i in range(repetitions):
        led.high()
        time.sleep(period_on)
        led.low()
        time.sleep(period_off)

def connect_to_socket():
    global s

    while True:
        try:
            s = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            s.settimeout(4)
            s.connect(("192.168.1.12",8500))
            
        except OSError as e:
            print("Could not connect to the socket:", e)
            s.close()
            blink(1,0.1,2)
            
        except Exception as e:
            print(type(e))
            print("Error occured while connecting to socket:", e)
            blink(1,0.1,2) 
        else:
            print("Connected to socket")
            break

def send_message(msg=""):
    global cnt
    try:
        # msg = f"hearbeat: {cnt}\n"
#         # msg = "testos\n"
        s.send(msg)
        led.high()
        time.sleep(0.1)
        led.low()
        cnt += 1

    except Exception as e:
        print("Error while sending msg:")
        print(type(e))
        print(e)
        time.sleep(2)
        raise
    else:
        print(f"{msg[:-1]} was sent to the socket") 
        
def connect_to_wifi():
    
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

def set_time():
    NTP_DELTA = 2208988800 - 3600
    host = "pool.ntp.org"
    NTP_QUERY = bytearray(48)
    NTP_QUERY[0] = 0x1B
    addr = socket.getaddrinfo(host, 123)[0][-1]
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.settimeout(1)
        res = s.sendto(NTP_QUERY, addr)
        msg = s.recv(48)
    finally:
        s.close()
    val = struct.unpack("!I", msg[40:44])[0]
    t = val - NTP_DELTA
    tm = time.gmtime(t)
    machine.RTC().datetime((tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5], 0))
    
    
# For demo purposes, we have an infinite loop here
# while True:
#     led.high()
#     time.sleep(0.5)
#     led.low()
#     time.sleep(0.5)
   
# connect_to _wifi()
#Socket
# connect_to_socket()

connect_to_wifi()
set_time()

i2c = I2C(0,scl=Pin(17), sda=Pin(16), freq=10000)
mcp = mcp9808.MCP9808(i2c)


while True:
    try:
        print(time.localtime())

        temp_celsius = mcp.get_temp()
        connect_to_socket()
        send_message(f"Temperature = {temp_celsius:.2f} C\n")
        s.close()
        time.sleep(5)
    except Exception:
        connect_to_wifi()

        
    
