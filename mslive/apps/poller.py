import time
from dataclasses import dataclass
import serial

REQ_GENERAL = bytes.fromhex("12 05 0B 03")
REQ_ECU_ID  = bytes.fromhex("12 04 00")

def xor_checksum(data: bytes) -> int:
    x = 0
    for b in data:
        x ^= b
    return x

@dataclass
class DS2Config:
    port: str
    baud: int = 9600
    timeout: float = 1.0
    inter_byte_timeout: float = 0.05
    debug: bool = False

class DS2:
    def __init__(self, cfg: DS2Config):
        self.cfg = cfg
        self.ser = None

    def open(self) -> None:
        self.ser = serial.Serial(
            port=self.cfg.port,
            baudrate=self.cfg.baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=self.cfg.timeout,
            inter_byte_timeout=self.cfg.inter_byte_timeout,
        )
        if self.cfg.debug:
            print(f"[DS2] Opened {self.cfg.port} at {self.cfg.baud} baud")

    def close(self) -> None:
        if self.ser:
            self.ser.close()
            self.ser = None

    def _read_exact(self, n: int) -> bytes:
        buf = bytearray()
        start = time.time()
        while len(buf) < n:
            chunk = self.ser.read(n - len(buf))
            if chunk:
                buf += chunk
                continue
            if time.time() - start > self.cfg.timeout:
                break
        return bytes(buf)

    def send(self, payload_no_chk: bytes) -> bytes:
        frame = payload_no_chk + bytes([xor_checksum(payload_no_chk)])

        # Clear stale data
        self.ser.reset_input_buffer()

        # TX
        self.ser.write(frame)
        self.ser.flush()
        time.sleep(0.02)

        # Echo handling (best-effort)
        if self.ser.in_waiting >= len(frame):
            echo = self._read_exact(len(frame))
            # Some interfaces may prepend junk; if you ever see that, we can harden this further.

        time.sleep(0.03)

        # RX header: [addr][len]
        hdr = self._read_exact(2)
        if len(hdr) < 2:
            raise TimeoutError("No DS2 response header received")

        addr, total_len = hdr[0], hdr[1]
        if total_len < 3 or total_len > 255:
            raise ValueError(f"Invalid response length: {total_len}")

        rest = self._read_exact(total_len - 2)
        resp = hdr + rest

        if len(resp) != total_len:
            raise TimeoutError(f"Incomplete DS2 response: got {len(resp)}/{total_len}")

        # XOR checksum verify
        exp = xor_checksum(resp[:-1])
        if resp[-1] != exp:
            raise ValueError("Bad checksum")

        return resp

def poll_general(port: str, seconds: float = 10.0, hz: float = 5.0):
    d = DS2(DS2Config(port=port, baud=9600, debug=False))
    d.open()

    # Give the USB cable a moment after plug-in / ignition-on
    time.sleep(1.0)

    period = 1.0 / hz
    t_end = time.time() + seconds

    try:
        while time.time() < t_end:
            t0 = time.time()
            resp = d.send(REQ_GENERAL)

            # resp format: [0]=0x12, [1]=len, [2]=status (a0/a1/ff), then payload bytes..., last is checksum
            status = resp[2]
            if status == 0xA0:
                yield resp
            # if ECU busy (0xA1) just skip

            dt = time.time() - t0
            if dt < period:
                time.sleep(period - dt)
    finally:
        d.close()
