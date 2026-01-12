import time
from dataclasses import dataclass
import serial

def xor_checksum(data: bytes) -> int:
    x = 0
    for b in data:
        x ^= b
    return x

@dataclass
class DS2Config:
    port: str
    baud: int = 10400
    timeout: float = 1.0
    inter_byte_timeout: float = 0.05

class DS2:
    """
    BMW DS2 over ISO9141 K-line via a USB serial (e.g., FT232 K+DCAN cable on K-line).
    Handles:
      - fast init (break low/high)
      - echo discard
      - length-based receive
      - XOR checksum verify
    """
    def __init__(self, cfg: DS2Config):
        self.cfg = cfg
        self.ser: serial.Serial | None = None

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

    def close(self) -> None:
        if self.ser:
            self.ser.close()
            self.ser = None

    def fast_init(self) -> None:
        """
        Typical K-line fast init: pull line low 25ms, high 25ms, then start comms.
        Using break_condition as a practical way to force TX low on many USB UARTs.
        """
        if not self.ser:
            raise RuntimeError("Serial not open")

        # ensure line idle high
        self.ser.break_condition = False
        time.sleep(0.35)  # "bus idle" guard (often helps)

        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()

        # Low 25ms
        self.ser.break_condition = True
        time.sleep(0.025)

        # High 25ms
        self.ser.break_condition = False
        time.sleep(0.025)

        # Small settle
        time.sleep(0.05)

    def _read_exact(self, n: int) -> bytes:
        if not self.ser:
            raise RuntimeError("Serial not open")
        buf = bytearray()
        while len(buf) < n:
            chunk = self.ser.read(n - len(buf))
            if not chunk:
                break
            buf += chunk
        return bytes(buf)

    def send(self, payload_no_chk: bytes) -> bytes:
        """
        payload_no_chk example from your trace: b'\\x12\\x05\\x0B\\x03'
        We append XOR checksum, write, discard echo, then read reply.
        """
        if not self.ser:
            raise RuntimeError("Serial not open")

        frame = payload_no_chk + bytes([xor_checksum(payload_no_chk)])

        # write frame
        self.ser.write(frame)
        self.ser.flush()

        # discard echo (DS2 echo characteristic)
        echo = self._read_exact(len(frame))
        # some adapters echo imperfectly; tolerate partial echo
# Discard echo only if it's actually there.
# On some setups there is no echo; blocking here can consume the ECU response.
        time.sleep(0.01)  # allow UART buffer to fill

        try:
            waiting = self.ser.in_waiting if self.ser else 0
        except Exception:
            waiting = 0

        if waiting >= len(frame):
            echo = self._read_exact(len(frame))
            # Optionally verify it matches what we sent; otherwise ignore.
        # read response header: addr + len
        hdr = self._read_exact(2)
        if len(hdr) < 2:
            raise TimeoutError("No DS2 response header received")

        addr, total_len = hdr[0], hdr[1]
        rest = self._read_exact(total_len - 2)
        resp = hdr + rest

        if len(resp) != total_len:
            raise TimeoutError(f"Incomplete DS2 response: got {len(resp)}/{total_len} bytes")

        # checksum verify
        if xor_checksum(resp[:-1]) != resp[-1]:
            raise ValueError(f"Bad checksum: resp={resp.hex(' ')}")

        return resp
