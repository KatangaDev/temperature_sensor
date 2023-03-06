import utime as time
from machine import Pin
from neopixel import NeoPixel

np = NeoPixel(Pin(2), 1)


def blink(period_on=0.1, period_off=0.3, repetitions=1, color='green', brightness=0.5):
    colors = {'red': (1.0, 0.0, 0.0),
              'green': (0.0, 1.0, 0.0),
              'blue': (0.0, 0.0, 1.0)}

    requested_param = tuple([int(x * brightness * 255) for x in colors[color]])

    for i in range(repetitions):
        np[0] = requested_param
        np.write()
        time.sleep(period_on)
        np[0] = (0, 0, 0)
        np.write()
        time.sleep(period_off)


while True:
    blink(1, 2, color='green')

