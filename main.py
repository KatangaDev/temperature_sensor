import time
import json
import uasyncio
import utime
import machine
from machine import Pin
import network
import usocket as socket
import struct
import wifi_config
import uasyncio as asyncio
from math import inf
import uselect as select
import ds_sensor
import areqs as requests

# region Constants
SAMPLING_PERIOD = 60 * 1
LOGGING_PERIOD = 3
BROADCAST_PERIOD = 60 * 10  # 60 * 5
HOTSPOT_TIME = 60 * 10  # seconds
WATCHDOG_MS = 1000 * 24 * 60 * 60  # 24 hours
# WATCHDOG_MS = 1000 * 60
# MAX_LOG_SIZE = 1024 * 10  # [Bytes]
MAX_LOG_SIZE = 1  # [Bytes]

SERVER_ADDRESS = "https://haccpapi.azurewebsites.net/Measurement/PostMeasurements"
# SERVER_ADDRESS = "https://192.168.0.144"


# endregion
class TimeTicks:
    def __init__(self):
        self.last_sensor_sample: int = 0
        self.last_broadcast: int = -BROADCAST_PERIOD * 1000
        self.power_up = utime.ticks_ms()

    def __call__(self, *args, **kwargs):
        print(self.last_sensor_sample, self.last_broadcast)


# region Global variables
ssid: str
password: str
machine_id = ""
time_ticks = TimeTicks()
led = Pin("LED", Pin.OUT)
# log_lock = _thread.allocate_lock()
log_lock = asyncio.Lock()
stop_sensor_thread = False
s: socket.Socket
cnt = 0
current_temperature: float = 0.0
last_sample_timestamp: str = ""

event_sensor_done_ = asyncio.Event()
broadcast_done = asyncio.Event()


# defining a decorator
def store_wifi_params(ssid, password):
    with open("settings.txt", "w") as f:
        f.write(f"{ssid.replace('+', ' ')}\n")
        f.write(f"{password}")
        f.flush()


def load_wifi_params():
    data = []
    try:
        with open("settings.txt", "r") as f:
            for line in f:
                data.append(line)
    except OSError:
        ssid = ""
        password = ""

    try:
        ssid = data[0]
        ssid = ssid.strip()
        password = data[1]
    except IndexError:
        ssid = ""
        password = ""

    print(ssid, password)
    return ssid, password


async def blink(period_on=0.1, period_off=0.3, repetitions=1):
    for i in range(repetitions):
        led.high()
        await asyncio.sleep(period_on)
        led.low()
        await asyncio.sleep(period_off)


async def blink_loop(stop_event: asyncio.Event, period_on=0.3, period_off=0.3):
    while not stop_event.is_set():
        led.high()
        await asyncio.sleep(period_on)
        led.low()
        await asyncio.sleep(period_off)


async def watchdog(stop_event: asyncio.Event, time_s=60):
    periods = 0
    while not stop_event.is_set():
        await asyncio.sleep(1)
        periods += 1
        if periods > time_s:
            print('Watchdog - rebooting')
            machine.reset()


async def send_message(msg=None, timeout=inf):
    global cnt
    success = False

    if msg is None:
        msg = {}

    try:
        start = utime.ticks_ms()
        print("Trying to send:")
        print(json.dumps(msg))

        res = await requests.post(SERVER_ADDRESS, json=msg, timeout=30)

        print(f"status code: {res.status_code}")
        if res.status_code != 200:
            print(res.text)

        res.close()
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
        print("Error while sending msg to the server:")
        print(type(e), e)

    else:
        print("Data was sent to server")
        success = True

    finally:
        return success


def connect_to_wifi(ssid, password):
    global wlan
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)
    i = 1

    connecting_start = time.time()
    while True:
        print(f"Connection attempt {i}")
        diff = time.time() - connecting_start
        if wlan.isconnected():
            print("Acquired IP address: " + wlan.ifconfig()[0])
            return True
        if diff > 5:
            wlan.active(False)
            print(f"Could not connect to |{ssid}| with |{password}|")
            return False

        time.sleep(2)
        i += 1


def set_time():
    print("Setting time using NTP server...")
    NTP_DELTA = 2208988800
    # NTP_DELTA = 2208988800 - 7200  # - 3600 instead of 7200 for winter time
    host = "pool.ntp.org"
    NTP_QUERY = bytearray(48)
    NTP_QUERY[0] = 0x1B

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        addr = socket.getaddrinfo(host, 123)[0][-1]
        s.settimeout(5)
        res = s.sendto(NTP_QUERY, addr)
        msg = s.recv(48)
    except OSError as e:
        print("Could not set machine time using NTP:")
        print(type(e), e)
        return False
    except Exception as e:
        print("Unknown exception")
        print(type(e), e)
        return False

    finally:
        s.close()

    val = struct.unpack("!I", msg[40:44])[0]
    t = val - NTP_DELTA
    tm = time.gmtime(t)
    machine.RTC().datetime((tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5], 0))

    print("Machine time set using NTP server")
    print(f"{tm[0]:04d}-{tm[1]:02d}-{tm[2]:02d} {tm[3]:02d}:{tm[4]:02d}:{tm[5]:02d}")

    return True


# @wrap_log
async def log_temperature(temp_sensor: ds_sensor.Sensor):
    await get_temperature(temp_sensor)

    async with log_lock:
        with open("temperature_log.txt", "a") as f:
            line = f"{last_sample_timestamp};{current_temperature:.1f}\n"
            f.write(line)

        with open("temperature_log.txt", "r") as f:
            log_size = f.read().count("\n")

        if log_size > MAX_LOG_SIZE:
            await remove_from_log()


async def get_temperature(temp_sensor: ds_sensor.Sensor):
    global current_temperature, last_sample_timestamp
    time_ticks.last_sensor_sample = utime.ticks_ms()

    current_temperature = await temp_sensor.get_temp()
    print(f"{current_temperature:.1f} C")
    t = time.localtime()
    friendly_time = f"{t[0]}-{t[1]:02d}-{t[2]:02d}T{t[3]:02d}:{t[4]:02d}:{t[5]:02d}Z"
    last_sample_timestamp = friendly_time


# @wrap_log
async def get_broad_data_to_send() -> (int, dict):
    data_to_send = {}
    async with log_lock:
        with open("temperature_log.txt", "r") as f:
            data = f.read().splitlines(True)[:200]
            data_to_send['id'] = machine_id
            data_to_send['location'] = 'L3'
            try:
                times, temps = list(zip(*[line.strip().split(";") for line in data]))
                temps = list(map(float, temps))
                data_to_send['measurements'] = [{"time": times[0], "temperature": temps[0]}]

            except ValueError:
                times, temps = [], []
                data_to_send['measurements'] = [{'time': times, "temperature": temps}]

    return len(temps), data_to_send


# @wrap_log
async def remove_from_log(no_of_lines=1):
    with open("temperature_log.txt", "r") as f:
        data = f.read().splitlines(True)
    with open("temperature_log.txt", "w") as f:
        for line in data[no_of_lines:]:
            f.write(line)
    print(f"{no_of_lines} removed from log")

    await uasyncio.sleep(0.05)


async def sensor_loop_as(sensor):
    await log_temperature(sensor)  # lock in the function


# @wrap_log
async def connect_and_send():
    time_ticks.last_broadcast = utime.ticks_ms()
    try:
        while True:
            number_of_lines, message = await get_broad_data_to_send()
            if number_of_lines > 0:
                if await send_message(message):
                    async with log_lock:
                        await remove_from_log(number_of_lines)
                else:
                    break
            else:
                break

    except RuntimeError as e:
        print(type(e), e)
    except Exception as e:
        print(type(e), e)
        pass
        # TODO: reconnection with wifi
        # connect_to_wifi(ssid, password)


def get_webserver_html(temperature, timestamp):
    html = f"""<!DOCTYPE html>
        <html>
        <body>

        <p>Temperature: {temperature:.1f} C</p>
        <p>Measured at {timestamp}</p>

        </body>
        </html>"""

    return html


async def webserver():
    addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
    socket_webserver = socket.socket()
    socket_webserver.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    socket_webserver.bind(addr)
    socket_webserver.listen(10)
    client = None

    poller = select.poll()
    poller.register(socket_webserver, select.POLLIN)

    print("Webserver task started...")

    while True:
        try:
            res = poller.poll(1)  # 1ms block
            if res:  # Only s_sock is polled
                client, addr = socket_webserver.accept()  # get client socket
            else:
                await asyncio.sleep_ms(200)
                continue

            print('client connected to webserver from', addr)

            client.send('HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n')
            client.send(get_webserver_html(current_temperature, last_sample_timestamp))
            await asyncio.sleep_ms(500)
            client.close()

        except OSError as e:
            if client:
                client.close()
            print('Connection closed unexpectedly')


def get_machine_id():
    from machine import unique_id
    from ubinascii import hexlify

    return hexlify(unique_id()).decode()


async def init():
    global sensor, machine_id
    led.high()
    machine_id = get_machine_id()

    with open("temperature_log.txt", "a") as f:
        pass

    # Connection loop
    request_wifi_params = False
    while True:
        ssid, password = load_wifi_params()
        if (not ssid) or (not password) or request_wifi_params:
            e_stop = asyncio.Event()
            wifi_config.start_ap()
            blink_loop_task = asyncio.create_task(blink_loop(e_stop))
            watchdog_task = asyncio.create_task(watchdog(e_stop, time_s=HOTSPOT_TIME))
            ssid, password = await wifi_config.get_config_data()
            wifi_config.stop_ap()
            e_stop.set()
            store_wifi_params(ssid, password)
            await asyncio.sleep(2)
            machine.reset()
        if connect_to_wifi(ssid, password):
            for i in range(1):
                if set_time():
                    break
            request_wifi_params = False
            break
        else:
            request_wifi_params = True

    sensor = ds_sensor.Sensor(Pin(21))
    init_temp = await get_temperature(sensor)
    led.low()
    time_ticks.power_up = utime.ticks_ms()


async def main():
    # global last_sensor_sample
    sensor_task, broadcast_task, webserver_task, tcpserver_task = None, None, None, None
    sensor_task = asyncio.create_task(sensor_loop_as(sensor))
    await asyncio.wait_for(sensor_task, 5)

    webserver_task = asyncio.create_task(webserver())
    # tcpserver_task = asyncio.create_task(tcpserver())

    while True:
        try:
            if utime.ticks_diff(utime.ticks_ms(), time_ticks.last_sensor_sample) > (SAMPLING_PERIOD * 1000):
                if sensor_task is not None:
                    await asyncio.wait_for(sensor_task, 2)
                sensor_task = asyncio.create_task(sensor_loop_as(sensor))
        except Exception as e:
            print(type(e), e)

        try:
            if utime.ticks_diff(utime.ticks_ms(), time_ticks.last_broadcast) > (BROADCAST_PERIOD * 1000):
                if broadcast_task is not None:
                    await asyncio.wait_for(broadcast_task, 15)
                broadcast_task = asyncio.create_task(connect_and_send())
        except TimeoutError as e:
            print('Broadcast task timeout. Awaiting...')

        await asyncio.sleep_ms(200)

        # Global watchdog
        if utime.ticks_diff(utime.ticks_ms(), time_ticks.power_up) > WATCHDOG_MS:
            print("Global watchdog reboot...")
            machine.reset()


asyncio.run(init())
asyncio.run(main())
# main()

# TODO: remove debug prints


