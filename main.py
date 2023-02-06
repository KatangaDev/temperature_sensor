import time
import machine
from machine import Pin
import network
import socket
from machine import I2C
import mcp9808
import struct
import wifi_config
import _thread

PERIOD = 600

led = Pin("LED", Pin.OUT)
log_lock = _thread.allocate_lock()

# ssid, password = "Monitoring109a", "vegaspalmas"

s: socket.Socket
cnt = 0

with open("temperature_log.txt", "a") as f:
    pass


# rtc = machine.RTC()
# rtc.datetime((2023, 1, 31, 1, 20, 9, 0, 0))
# print(rtc.datetime())


def store_wifi_params(ssid, password):
    with open("settings.txt", "w") as f:
        f.write(f"{ssid}\n")
        f.write(f"{password}")
        f.flush()


def load_wifi_params():
    data = []
    with open("settings.txt", "r") as f:
        for line in f:
            data.append(line)

    try:
        ssid = data[0]
        ssid = ssid.strip()
        password = data[1]
    except IndexError:
        ssid = ""
        password = ""

    return ssid, password


def blink(period_on=0.1, period_off=0.3, repetitions=1):
    for i in range(repetitions):
        led.high()
        time.sleep(period_on)
        led.low()
        time.sleep(period_off)


def connect_to_socket():
    global s

    for i in range(3):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(4)
            s.connect(("192.168.1.12", 8500))

        except OSError as e:
            print("Could not connect to the socket:", e)
            s.close()
            blink(1, 0.1, 2)

        except Exception as e:
            print(type(e))
            print("Error occured while connecting to socket:", e)
            blink(1, 0.1, 2)
        else:
            print("Connected to socket")
            return True

    return False


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
        return True


def connect_to_wifi(ssid, password):
    global wlan
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)

    connecting_start = time.time()
    while True:
        diff = time.time() - connecting_start
        if wlan.isconnected():
            return True
        if diff > 20:
            wlan.active(False)
            return False

        time.sleep(2)


def set_time():
    print("Setting time using NTP server...")
    NTP_DELTA = 2208988800 - 3600
    host = "pool.ntp.org"
    NTP_QUERY = bytearray(48)
    NTP_QUERY[0] = 0x1B
    addr = socket.getaddrinfo(host, 123)[0][-1]
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.settimeout(5)
        res = s.sendto(NTP_QUERY, addr)
        msg = s.recv(48)
    except OSError as e:
        print(type(e),e)
        return

    finally:
        s.close()
    val = struct.unpack("!I", msg[40:44])[0]
    t = val - NTP_DELTA
    tm = time.gmtime(t)
    machine.RTC().datetime((tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5], 0))
    print("Machine time set using NTP server")


def log_temperature():
    temp_celsius = mcp.get_temp()
    t = time.localtime()
    friendly_time = f"{t[0]}-{t[1]:02d}-{t[2]:02d} {t[3]:02d}:{t[4]:02d}:{t[5]:02d}"
    log_lock.acquire()
    with open("temperature_log.txt", "a") as f:
        line = f"{friendly_time} temperature = {temp_celsius:.1f} C\n"
        f.write(line)
    log_lock.release()


def get_data_to_send():
    log_lock.acquire()
    with open("temperature_log.txt", "r") as f:
        line = f.readline()
    log_lock.release()
    return line


def remove_first_from_log():
    log_lock.acquire()
    with open("temperature_log.txt", "r") as f:
        data = f.read().splitlines(True)
    with open("temperature_log.txt", "w") as f:
        for line in data[1:]:
            f.write(line)
    log_lock.release()


def sensor_loop():
    while True:
        log_temperature()  # lock in the function
        time.sleep(PERIOD)




# Connection loop
request_wifi_params = False
while True:
    ssid, password = load_wifi_params()
    if (not ssid) or (not password) or request_wifi_params:
        wifi_config.start_ap()
        ssid, password = wifi_config.get_config_data()
        wifi_config.stop_ap()
        store_wifi_params(ssid, password)
    if connect_to_wifi(ssid, password):
        set_time()
        request_wifi_params = False
        break
    else:
        request_wifi_params = True

i2c = I2C(0, scl=Pin(17), sda=Pin(16), freq=10000)
mcp = mcp9808.MCP9808(i2c)
sensor_thread = _thread.start_new_thread(sensor_loop,tuple())

while True:
    try:
        if not connect_to_socket():
            raise RuntimeError
        while True:
            message = get_data_to_send()
            if message:
                if send_message(message):
                    remove_first_from_log()

            else:
                s.close()
                break
        time.sleep(3600)
    except RuntimeError as e:
        print(type(e),e)
        time.sleep(60)
    except Exception as e:
        print(type(e),e)
        connect_to_wifi(ssid, password)

