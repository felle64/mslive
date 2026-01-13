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
    baud: int = 9600
    timeout: float = 1.5
    inter_byte_timeout: float = 0.05
    debug: bool = False

class DS2:
    """
    BMW DS2 over ISO9141 K-line via K+DCAN cable.
    """
    def __init__(self, cfg: DS2Config):
        self.cfg = cfg
        self.ser: serial.Serial | None = None
        self.initialized = False

    def open(self) -> None:
        self.ser = serial.Serial(
            port=self.cfg.port,
            baudrate=self.cfg.baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_EVEN,
            stopbits=serial.STOPBITS_ONE,
            timeout=self.cfg.timeout,
            inter_byte_timeout=self.cfg.inter_byte_timeout,
        )
        if self.cfg.debug:
            print(f"[DS2] Opened {self.cfg.port} at {self.cfg.baud} baud")
        
        # Give cable time to settle
        time.sleep(0.5)

    def close(self) -> None:
        if self.ser:
            self.ser.close()
            self.ser = None

    def _read_exact(self, n: int) -> bytes:
        if not self.ser:
            raise RuntimeError("Serial not open")
        buf = bytearray()
        start_time = time.time()
        while len(buf) < n:
            chunk = self.ser.read(n - len(buf))
            if not chunk:
                if time.time() - start_time > self.cfg.timeout:
                    if self.cfg.debug:
                        print(f"[DS2] Timeout reading {n} bytes, got {len(buf)}: {buf.hex(' ') if buf else '(empty)'}")
                    break
            else:
                buf += chunk
        return bytes(buf)

    def init_ecu(self) -> bool:
        """
        Initialize communication with ECU.
        DS2 typically uses start communication request.
        """
        if not self.ser:
            raise RuntimeError("Serial not open")
        
        if self.cfg.debug:
            print("[DS2] Starting ECU init...")
        
        # Clear buffers
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        
        # DS2 Start Communication: 0x81 (addr 0x12 + 0x81 service)
        # Format: [dest_addr] [length] [service] [checksum]
        init_msg = bytes([0x12, 0x04, 0x81, 0x12 ^ 0x04 ^ 0x81])
        
        if self.cfg.debug:
            print(f"[DS2] Init TX: {init_msg.hex(' ')}")
        
        self.ser.write(init_msg)
        self.ser.flush()
        time.sleep(0.05)
        
        # Discard echo
        waiting = self.ser.in_waiting if self.ser else 0
        if waiting >= len(init_msg):
            echo = self._read_exact(len(init_msg))
            if self.cfg.debug:
                print(f"[DS2] Init echo: {echo.hex(' ')}")
        
        # Wait for response
        time.sleep(0.1)
        
        waiting = self.ser.in_waiting if self.ser else 0
        if self.cfg.debug:
            print(f"[DS2] Bytes waiting after init: {waiting}")
        
        if waiting > 0:
            # Read header
            hdr = self._read_exact(2)
            if len(hdr) == 2:
                addr, total_len = hdr[0], hdr[1]
                if self.cfg.debug:
                    print(f"[DS2] Init response header: addr=0x{addr:02X}, len={total_len}")
                
                # Read rest of message
                rest = self._read_exact(total_len - 2)
                resp = hdr + rest
                
                if self.cfg.debug:
                    print(f"[DS2] Init response: {resp.hex(' ')}")
                
                # If we got a valid response, consider initialized
                if len(resp) == total_len:
                    self.initialized = True
                    return True
        
        if self.cfg.debug:
            print("[DS2] Init failed - no response")
        
        return False

    def send(self, payload_no_chk: bytes) -> bytes:
        """
        Send a DS2 request and receive response.
        payload_no_chk: [dest_addr] [service] [data...]
        """
        if not self.ser:
            raise RuntimeError("Serial not open")
        
        if not self.initialized:
            if self.cfg.debug:
                print("[DS2] Not initialized, attempting init...")
            if not self.init_ecu():
                raise RuntimeError("Failed to initialize ECU communication")

        frame = payload_no_chk + bytes([xor_checksum(payload_no_chk)])
        
        if self.cfg.debug:
            print(f"[DS2] TX ({len(frame)} bytes): {frame.hex(' ')}")
        
        # Clear stale data
        self.ser.reset_input_buffer()
        
        # Write frame
        self.ser.write(frame)
        self.ser.flush()
        
        # Wait for echo/response
        time.sleep(0.05)
        
        if self.cfg.debug:
            waiting = self.ser.in_waiting if self.ser else 0
            print(f"[DS2] Bytes waiting after TX: {waiting}")
        
        # Handle echo
        waiting = self.ser.in_waiting if self.ser else 0
        if waiting >= len(frame):
            echo = self._read_exact(len(frame))
            if self.cfg.debug:
                print(f"[DS2] Echo ({len(echo)} bytes): {echo.hex(' ')}")
            waiting -= len(frame)
        
        # Wait a bit more for ECU response
        if waiting == 0:
            time.sleep(0.1)
        
        if self.cfg.debug:
            waiting = self.ser.in_waiting if self.ser else 0
            print(f"[DS2] Bytes waiting before RX: {waiting}")
        
        # Read response header
        hdr = self._read_exact(2)
        if len(hdr) < 2:
            if self.cfg.debug:
                print(f"[DS2] ERROR: No response header (got {len(hdr)} bytes)")
                extra = self.ser.read(100)
                if extra:
                    print(f"[DS2] Raw buffer: {extra.hex(' ')}")
            raise TimeoutError("No DS2 response header received")
        
        addr, total_len = hdr[0], hdr[1]
        
        if self.cfg.debug:
            print(f"[DS2] Response header: addr=0x{addr:02X}, len={total_len}")
        
        if total_len < 3 or total_len > 255:
            raise ValueError(f"Invalid response length: {total_len}")
        
        rest = self._read_exact(total_len - 2)
        resp = hdr + rest
        
        if len(resp) != total_len:
            if self.cfg.debug:
                print(f"[DS2] Incomplete response: {resp.hex(' ')}")
            raise TimeoutError(f"Incomplete DS2 response: got {len(resp)}/{total_len} bytes")
        
        if self.cfg.debug:
            print(f"[DS2] RX ({len(resp)} bytes): {resp.hex(' ')}")
        
        # Verify checksum
        expected_chk = xor_checksum(resp[:-1])
        actual_chk = resp[-1]
        if expected_chk != actual_chk:
            if self.cfg.debug:
                print(f"[DS2] Checksum error: expected 0x{expected_chk:02X}, got 0x{actual_chk:02X}")
            raise ValueError(f"Bad checksum: resp={resp.hex(' ')}")
        
        return resp