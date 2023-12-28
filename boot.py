import urequests as requests
# import areqs as requests
import utime as time
import network
from machine import Pin, reset

RECONN_ATTEMPTS_REBOOT = 3
UPDATE = True


def main():
    led = Pin("LED", Pin.OUT)

    led.high()
    time.sleep(0.2)
    led.low()
    time.sleep(0.2)
    led.high()
    # return
    with open("settings.txt", "r") as f:
        ssid, password = f.read().split('\n')
        print(ssid, password)

    time.sleep(1)

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    for attempt in range(1, 4):
        try:
            print(f'Trying to connect, attempt {attempt}...')
            wlan.connect(ssid, password)
            if not wlan.isconnected():
                raise OSError

        except OSError as e:
            print(type(e), e)
            time.sleep(1)
        else:
            print("Connected to Wi-Fi")
            break
    else:
        print('Could not connect to Wi-Fi...')

        try:
            with open("temp.db", "r") as f:
                str = f.read().strip()

            retries = int(str) if len(str) > 0 else 0

            if retries >= RECONN_ATTEMPTS_REBOOT:
                print('Could not connect to Wi-Fi too many times. Initialization mode on.')
                retries = -1
                return

            else:
                print('Controller will be rebooted...')
                with open("temp.db", "w") as f:
                    f.write(f"{retries + 1}")
                reset()

        except FileNotFoundError:
            print('file not found')
            retries = 0

        except Exception as e:
            print('unknown')
            retries = 0
            print(type(e), e)

        finally:
            print('finally ')
            with open("temp.db", "w") as f:
                f.write(f"{retries + 1}")

    # while not wlan.isconnected():
    #     time.sleep(1)
    #     print(wlan.isconnected())

    # r = urequests.get("https://raw.githubusercontent.com/KatangaDev/temperature_sensor/ota_pico/main.py",headers={'User-Agent':'KatangaDev'})
    if not UPDATE:
        return

    print("Checking for updates...")
    r = requests.get("https://raw.githubusercontent.com/KatangaDev/temperature_sensor/ota_pico/main.py",
                     headers={'User-Agent': 'KatangaDev'})
    try:
        print("updating...")
        new_file = open("main.py", 'w')
        # new_file.write(r.content.decode('utf-8'))
        new_file.write(r.text)
        new_file.close()
        print("File written")

    except:
        print('decode fail try adding non-code files to .gitignore')
        try:
            new_file.close()
        except:
            print('tried to close new_file to save memory during raw file decode')


main()

