import time
from mslive.core.ds2 import DS2, DS2Config

REQ_GENERAL = bytes.fromhex("12 05 0B 03")

OIL_M = 0.796098
OIL_B = -48.0137

def decode(resp: bytes) -> dict:
    rpm = (resp[3] << 8) | resp[4]
    oil_c = resp[12] * OIL_M + OIL_B
    return rpm, oil_c, resp[12]

d = DS2(DS2Config(port="COM1", baud=9600, timeout=2.0, debug=False))
d.open()
print("ts,rpm,oil_c,raw12")
try:
    while True:
        r = d.send(REQ_GENERAL)
        rpm, oil_c, raw12 = decode(r)
        print(f"{time.time():.3f},{rpm},{oil_c:.1f},{raw12}")
        time.sleep(0.10)
finally:
    d.close()
