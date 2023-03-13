import utime as time
from machine import Pin


led = Pin("LED", Pin.OUT)


def blink(period_on=0.1, period_off=0.3, repetitions=1):
    for i in range(repetitions):
        led.high()
        time.sleep(period_on)
        led.low()
        time.sleep(period_off)


while True:
    blink(2, 2)

