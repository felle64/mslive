from mslive.core.ds2 import DS2, DS2Config

REQ_ECU_ID = bytes.fromhex("12 04 00")        # DS2 payload; ds2.py appends XOR checksum
REQ_GENERAL = bytes.fromhex("12 05 0B 03")

d = DS2(DS2Config(port="COM1", baud=9600, timeout=1.5))
d.open()

# optional: some setups work without init; keep it for now
d.fast_init()

print("ECU ID:", d.send(REQ_ECU_ID).hex(" "))
print("GEN  :", d.send(REQ_GENERAL).hex(" "))

d.close()
