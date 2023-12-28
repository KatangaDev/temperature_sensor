#import urequests
import areqs as requests
import utime as time
import network
# import micropython
from machine import Pin

def main():
    led = Pin("LED", Pin.OUT)
    led.high()
    time.sleep(1)
    led.low()
    #return
    with open("settings.txt","r") as f:
        ssid,password = f.read().split('\n')
        print(ssid,password)

    time.sleep(1)

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    while True:
        try:
            wlan.connect(ssid, password)

        except OSError as e:
            print(type(e),e)
            time.sleep(1)
        else:
            print("Connected?")
            break

    while not wlan.isconnected():
        time.sleep(1)
        print(wlan.isconnected())


    # r = urequests.get("https://raw.githubusercontent.com/KatangaDev/temperature_sensor/ota_pico/main.py",headers={'User-Agent':'KatangaDev'})
    print("Checking for updates...")
    r = requests.get("https://raw.githubusercontent.com/KatangaDev/temperature_sensor/ota_pico/main.py",headers={'User-Agent':'KatangaDev'})
    try:
        print("updating...")
        new_file = open("main2.py", 'w')
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
    #
    print('leaving boot')

main()
