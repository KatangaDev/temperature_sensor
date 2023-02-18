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
import os
import uasyncio as asyncio

# region Constants
SAMPLING_PERIOD = 60 * 3
BROADCAST_PERIOD = 5 # 60 * 5
MAX_LOG_SIZE = 1024 * 128  # [Bytes]
# endregion

# region Global variables
mcp_sensor:mcp9808.MCP9808
ssid:str
password:str
led = Pin("LED", Pin.OUT)
# log_lock = _thread.allocate_lock()
log_lock = asyncio.Lock()
stop_sensor_thread = False
s: socket.Socket
cnt = 0

# endregion

# region Overwriting
# ssid, password = "Monitoring109a", "vegaspalmas"

# endregion

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
            addr_ip = socket.getaddrinfo("Siek", 80)[0][-1][0]
            print(addr_ip)
            s.connect((addr_ip, 8500))
            # s.connect(("192.168.1.12", 8500))

        except OSError as e:
            print("Could not connect to the socket:", e)
            s.close()
            blink(1, 0.1, 2)

        except Exception as e:
            print(type(e))
            print("Error occured while connecting to socket:", e)
            blink(1, 0.1, 2)
        else:
            print("Connected to socket ")
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
        print(type(e), e)
        return

    finally:
        s.close()
    val = struct.unpack("!I", msg[40:44])[0]
    t = val - NTP_DELTA
    tm = time.gmtime(t)
    machine.RTC().datetime((tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5], 0))
    print("Machine time set using NTP server")


async def log_temperature(sensor:mcp9808.MCP9808):
    print("lock in log temp:", log_lock.locked())
    temp_celsius = sensor.get_temp()
    t = time.localtime()
    friendly_time = f"{t[0]}-{t[1]:02d}-{t[2]:02d} {t[3]:02d}:{t[4]:02d}:{t[5]:02d}"
    await log_lock.acquire()
    print("lock:",log_lock.locked())

    with open("temperature_log.txt", "a") as f:
        line = f"{friendly_time} temperature = {temp_celsius:.1f} C\n"
        f.write(line)

    log_size = os.stat("temperature_log.txt")[6]
    if log_size > MAX_LOG_SIZE:
        remove_from_log(log_acquired=True)

    print("Temperature logged")
    log_lock.release()


def get_data_to_send():
    log_lock.acquire()
    with open("temperature_log.txt", "r") as f:
        line = f.readline()
    log_lock.release()
    return line


def get_broad_data_to_send() -> (int, str):
    log_lock.acquire()
    with open("temperature_log.txt", "r") as f:
        data = f.read().splitlines(True)[:20]
        data_to_send = "".join(data)
    log_lock.release()
    return data_to_send.count('\n'), data_to_send


def remove_from_log(no_of_lines=1, log_acquired=False):
    if not log_acquired:
        log_lock.acquire()

    with open("temperature_log.txt", "r") as f:
        data = f.read().splitlines(True)
    with open("temperature_log.txt", "w") as f:
        for line in data[no_of_lines:]:
            f.write(line)

    if not log_acquired:
        log_lock.release()


def sensor_loop(sensor):
    while True:
        log_temperature(sensor)  # lock in the function
        time.sleep(SAMPLING_PERIOD)


async def sensor_loop_as(sensor):
    print("in sensor_loop_as",sensor)
    while True:
        await log_temperature(sensor)  # lock in the function
        # await simple_print()
        await asyncio.sleep(SAMPLING_PERIOD)


def init():
    global mcp_sensor

    with open("temperature_log.txt", "a") as f:
        pass

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
    mcp_sensor = mcp9808.MCP9808(i2c)


# noinspection PyAsyncCall
async def main():

    asyncio.create_task(sensor_loop_as(mcp_sensor))
    await asyncio.sleep(1)

    while True:
        await asyncio.sleep(5)
        try:
            if not connect_to_socket():
                raise RuntimeError
            while True:
                # message = get_data_to_send()
                number_of_lines, message = get_broad_data_to_send()
                if message:
                    if send_message(message):
                        remove_from_log(number_of_lines)
                        time.sleep(1)

                else:
                    s.close()
                    break
            time.sleep(BROADCAST_PERIOD)
        except RuntimeError as e:
            print(type(e), e)
            time.sleep(BROADCAST_PERIOD)
        except Exception as e:
            print(type(e), e)
            connect_to_wifi(ssid, password)


init()
asyncio.run(main())
# main()
