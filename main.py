import time

import uasyncio
import utime
import machine
from machine import Pin
import network
# import socket
import usocket as socket
from machine import I2C
import mcp9808
import struct
import wifi_config
import _thread
import os
import uasyncio as asyncio
from math import inf
from ucollections import namedtuple


# region Constants
SAMPLING_PERIOD = 10
BROADCAST_PERIOD = 30  # 60 * 5
MAX_LOG_SIZE = 1024 * 80  # [Bytes]
last_sensor_sample = 0
# endregion
class TimeTicks:
    def __init__(self):
        self.last_sensor_sample: int = 0
        self.last_broadcast: int = 0

    def __call__(self, *args, **kwargs):
        print(self.last_sensor_sample,self.last_broadcast)

# region Global variables
mcp_sensor: mcp9808.MCP9808
ssid: str
password: str
time_ticks = TimeTicks()
led = Pin("LED", Pin.OUT)
# log_lock = _thread.allocate_lock()
log_lock = asyncio.Lock()
stop_sensor_thread = False
s: socket.Socket
cnt = 0

event_sensor_done_ = asyncio.Event()
broadcast_done = asyncio.Event()


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


async def blink(period_on=0.1, period_off=0.3, repetitions=1):
    for i in range(repetitions):
        led.high()
        await asyncio.sleep(period_on)
        led.low()
        await asyncio.sleep(period_off)


async def connect_to_socket():
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
            await blink(0.1, 0.1, 2)

        except Exception as e:
            print("Error occured while connecting to socket:", type(e),e)
            await blink(0.1, 0.1, 2)
        else:
            print("Connected to socket ")
            return True

    return False


async def send_message(msg="",timeout=inf):
    global cnt
    success = False

    try:
        start = utime.ticks_ms()
        print("Trying to send message...")
        s.send(msg)
        await asyncio.sleep_ms(100)
        if utime.ticks_diff(utime.ticks_ms(), start) > timeout:
            raise OSError("send_message: timeout occurred")

        led.high()
        await asyncio.sleep(0.1)
        led.low()
        await asyncio.sleep(0.1)
        cnt += 1

    except OSError as e:
        print(e)
        await asyncio.sleep(2)

    except Exception as e:
        print("Error while sending msg:")
        print(type(e),e)
        raise

    else:
        print(f"{msg[:-1]} was sent to the socket")
        success = True
        return True

    finally:
        if not success:
            raise


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


async def log_temperature(sensor: mcp9808.MCP9808):
    time_ticks.last_sensor_sample = utime.ticks_ms()
    print("lock in log temp:", log_lock.locked())
    # await sensor.get_temp()
    temp_celsius = 0
    temp_celsius = sensor.get_temp()
    # print(temp_celsius)
    await asyncio.sleep(0.1)
    print(temp_celsius)
    t = time.localtime()
    friendly_time = f"{t[0]}-{t[1]:02d}-{t[2]:02d} {t[3]:02d}:{t[4]:02d}:{t[5]:02d}"

    print("lock waiting to acquire in log_temp")
    await log_lock.acquire()
    print("log acquired by log_temp")
    # print("lock:", log_lock.locked())

    with open("temperature_log.txt", "a") as f:
        line = f"{friendly_time} temperature = {temp_celsius:.1f} C\n"
        f.write(line)

    log_size = os.stat("temperature_log.txt")[6]
    if log_size > MAX_LOG_SIZE:
        await remove_from_log()

    print("Temperature logged")
    log_lock.release()

    print("lock released in log_temp")


# def get_data_to_send():
#     log_lock.acquire()
#     with open("temperature_log.txt", "r") as f:
#         line = f.readline()
#     log_lock.release()
#     return line


async def get_broad_data_to_send() -> (int, str):
    print("lock waiting to acquire in get_data_to_send")
    await log_lock.acquire()
    print("lock acquired in get_data_to_send")
    with open("temperature_log.txt", "r") as f:
        data = f.read().splitlines(True)[:20]
        data_to_send = "".join(data)
    await uasyncio.sleep(0.1)
    log_lock.release()
    print("lock released in get_data_to_send")

    return data_to_send.count('\n'), data_to_send



async def remove_from_log(no_of_lines=1):
    print("in remove_from_log")

    with open("temperature_log.txt", "r") as f:
        data = f.read().splitlines(True)
    with open("temperature_log.txt", "w") as f:
        for line in data[no_of_lines:]:
              f.write(line)

    print("before sleep in remove_from_log")
    await uasyncio.sleep(0.05)

# def sensor_loop(sensor):
#     while True:
#         log_temperature(sensor)  # lock in the function
#         time.sleep(SAMPLING_PERIOD)


async def sensor_loop_as(sensor):
    await log_temperature(sensor)  # lock in the function


async def connect_and_send():
    time_ticks.last_broadcast = utime.ticks_ms()
    try:
        if not await connect_to_socket():
            raise RuntimeError
        while True:
            # message = get_data_to_send()
            number_of_lines, message = await get_broad_data_to_send()
            if message:
                if await send_message(message):
                    print("lock waiting to acquire in connect and send")
                    await log_lock.acquire()
                    print("Locked by connect and send")
                    await remove_from_log(number_of_lines)
                    log_lock.release()
                    print("released by connect and send")
                    # await asyncio.sleep(0.1)

            else:
                s.close()
                # await asyncio.sleep(0.1)
                break
    except RuntimeError as e:
        print(type(e), e)
    except Exception as e:
        print(type(e), e)
        pass
        # TODO: reconnection with wifi
        # connect_to_wifi(ssid, password)


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
    # global last_sensor_sample
    sensor_task, broadcast_task = None, None

    while True:
        try:
            if utime.ticks_diff(utime.ticks_ms(), time_ticks.last_sensor_sample) > (SAMPLING_PERIOD * 1000):
                if sensor_task is not None:
                    await asyncio.wait_for(sensor_task,2)
                sensor_task = asyncio.create_task(sensor_loop_as(mcp_sensor))
        except Exception as e:
            print(type(e),e)

        try:
            if utime.ticks_diff(utime.ticks_ms(), time_ticks.last_broadcast) > (BROADCAST_PERIOD * 1000):
                if broadcast_task is not None:
                    await asyncio.wait_for(broadcast_task,5)
                broadcast_task = asyncio.create_task(connect_and_send())
        except TimeoutError as e:
            print('Broadcast task timeout. Awaiting...')

        await asyncio.sleep_ms(5000)


init()
asyncio.run(main())
# main()

# TODO: remove debug prints