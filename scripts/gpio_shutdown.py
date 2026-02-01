#!/usr/bin/env python3
import time
import os
import signal
import sys

try:
    import RPi.GPIO as GPIO
except ImportError:
    print("RPi.GPIO not installed. Install with: sudo apt install python3-rpi.gpio")
    sys.exit(1)

GPIO_PIN = 17          # BCM numbering (GPIO17 = physical pin 11)
HOLD_SECONDS = 1.2     # press-and-hold time before shutdown
POLL_HZ = 50           # polling frequency (low CPU)

def shutdown():
    # Use systemd shutdown (safe)
    os.system("systemctl poweroff")

def main():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(GPIO_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    press_t0 = None

    try:
        while True:
            pressed = (GPIO.input(GPIO_PIN) == GPIO.LOW)

            now = time.monotonic()
            if pressed:
                if press_t0 is None:
                    press_t0 = now
                elif (now - press_t0) >= HOLD_SECONDS:
                    shutdown()
                    time.sleep(5)  # if shutdown fails, don't spam
                    press_t0 = None
            else:
                press_t0 = None

            time.sleep(1.0 / POLL_HZ)

    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
