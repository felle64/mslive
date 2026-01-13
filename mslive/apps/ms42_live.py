# mslive/apps/ms42_live.py
import time
from dataclasses import dataclass
from typing import Optional

from mslive.core.ds2 import DS2, DS2Config

REQ_ECU_ID = bytes.fromhex("12 04 00")
REQ_GENERAL = bytes.fromhex("12 05 0B 03")

OIL_M = 0.796098
OIL_B = -48.0137


@dataclass
class LiveSample:
    ts: float
    rpm: float
    temp_x_c: float
    raw_temp_x: int


class MS42Live:
    """
    Thin wrapper around your proven DS2 implementation.
    Adds: wake/retry + reconnect logic.
    """
    def __init__(self, port: str, baud: int = 9600, debug: bool = False):
        self.port = port
        self.baud = baud
        self.debug = debug
        self.d: Optional[DS2] = None

    def open(self) -> None:
        self.d = DS2(DS2Config(port=self.port, baud=self.baud, debug=self.debug))
        self.d.open()
        # Give cable/ECU a moment
        time.sleep(0.8)

        # Prime comms (helps after key-cycles)
        try:
            self.d.send(REQ_ECU_ID)
        except Exception:
            # Don't fail the whole session; we’ll recover during polling
            pass

    def close(self) -> None:
        if self.d:
            try:
                self.d.close()
            finally:
                self.d = None

    def _slow_init_5baud(self, addr: int = 0x12) -> None:
        """
        Bit-bang 5-baud init using break_condition.
        Works on many FTDI K-line setups to wake ECU after a key-cycle.
        """
        if not self.d or not getattr(self.d, "ser", None):
            return

        ser = self.d.ser
        bit_time = 0.200  # 5 baud

        try:
            ser.break_condition = False
            time.sleep(0.300)

            ser.reset_input_buffer()
            ser.reset_output_buffer()

            # Start bit (0) => low
            ser.break_condition = True
            time.sleep(bit_time)

            # 8 data bits LSB-first
            for i in range(8):
                bit = (addr >> i) & 1
                ser.break_condition = (bit == 0)
                time.sleep(bit_time)

            # Stop bit (1) => high
            ser.break_condition = False
            time.sleep(bit_time)

            time.sleep(0.300)

            # Drain anything (sync bytes etc.)
            try:
                ser.read(64)
            except Exception:
                pass
        except Exception:
            # If break_condition isn't supported by that driver, just ignore
            pass

    def _send_with_recovery(self, payload: bytes) -> bytes:
        """
        Try once. If timeout, wake ECU and retry once.
        """
        if not self.d:
            raise RuntimeError("Not open")

        try:
            return self.d.send(payload)
        except TimeoutError:
            self._slow_init_5baud(0x12)
            time.sleep(0.2)
            return self.d.send(payload)

    @staticmethod
    def decode_general(resp: bytes) -> LiveSample:
        # RPM confirmed from your logs: resp[3:5] big-endian, no /2
        rpm = float((resp[3] << 8) | resp[4])

        # “TempX”: currently using the linear scaling you tested.
        # Keep it generic until you validate whether it’s oil/coolant/IAT.
        raw = resp[12]
        temp_x = raw * OIL_M + OIL_B

        return LiveSample(ts=time.time(), rpm=rpm, temp_x_c=float(temp_x), raw_temp_x=int(raw))

    def read_general(self) -> LiveSample:
        resp = self._send_with_recovery(REQ_GENERAL)
        return self.decode_general(resp)

    def stream_general(self, hz: float = 6.0):
        """
        Generator yielding LiveSample at a target rate, with auto-reconnect.
        """
        period = 1.0 / hz
        while True:
            t0 = time.time()

            # Ensure connected
            if not self.d:
                self.open()

            try:
                yield self.read_general()
            except Exception:
                # Reconnect on any failure
                self.close()
                time.sleep(0.8)

            dt = time.time() - t0
            if dt < period:
                time.sleep(period - dt)
