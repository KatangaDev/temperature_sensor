import utime as time
from machine import Pin,reset
from neopixel import NeoPixel
import senko
import network


np = NeoPixel(Pin(2),1)
# led = Pin("LED", Pin.OUT)

with open("settings.txt","r") as f:
    ssid,password = f.read().splitlines(False)

# time.sleep(3)

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(ssid, password)
time.sleep(1)

print(wlan.isconnected())



def blink(period_on=0.1, period_off=0.3, repetitions=1, color='green', brightness=0.5):
    colors = {'red': (1.0, 0.0, 0.0),
              'green': (0.0, 1.0, 0.0),
              'blue': (0.0, 0.0, 1.0)}

    requested_param = tuple([int(x*brightness*255) for x in colors[color]])

    for i in range(repetitions):
        np[0] = requested_param
        np.write()
        time.sleep(period_on)
        np[0] = (0, 0, 0)
        np.write()
        time.sleep(period_off)

# OTA = senko.Senko(
#   user="KatangaDev", # Required
#   repo="temperature_sensor", # Required
#   branch="ota_test_esp", # Optional: Defaults to "master"
#   working_dir="", # Optional: Defaults to "app"
#   files=["main.py"]
# )

# GITHUB_URL = "https://github.com/KatangaDev/temperature_sensor/tree/ota_test_esp"
# OTA = senko.Senko(url=GITHUB_URL, files=["main.py"])

OTA = senko.Senko(
  user="KatangaDev", repo="temperature_sensor",branch="ota_test_esp", files=["main.py"]
)

if OTA.update():
    print("Updated to the latest version! Rebooting...")
    reset()

while True:


    blink(0.1,0.9, color='blue')
    blink(0.1, 0.9, color='red')
