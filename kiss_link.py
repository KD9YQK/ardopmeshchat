"""
KISS link-layer wrapper around the `kiss3` (module `kiss`) library.

Provides:
- Background RX/TX threads
- Reconnect with backoff
- Simple `send(frame_bytes)` API

No application logic here; it just moves bytes.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Callable, Optional, Protocol, runtime_checkable

from kiss import SerialKISS, TCPKISS  # from the kiss3 package

from mesh_config import KISSConnectionConfig, TransportType

LOG = logging.getLogger(__name__)


class KISSClientError(Exception):
    """Base exception for KISSClient."""


@runtime_checkable
class KISSInterface(Protocol):
    """
    Structural type for KISS implementations.

    SerialKISS and TCPKISS from the `kiss` module should both satisfy this.
    """

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def read(self, callback: Callable[[bytes], None]) -> None: ...

    def write(self, frame: bytes) -> None: ...


class KISSClient:
    """
    Wrapper around kiss3's KISS classes.

    - Manages connection (Serial or TCP).
    - Runs RX and TX loops on background threads.
    - Exposes `send()` for raw AX.25 frame bytes (KISS payload).
    - Invokes user-supplied `rx_callback` for each received frame.
    """

    def __init__(
        self,
        config: KISSConnectionConfig,
        rx_callback: Callable[[bytes], None],
        name: str = "kiss3-client",
    ) -> None:
        self._config = config
        self._rx_callback = rx_callback
        self._name = name

        self._kiss_iface: Optional[KISSInterface] = None
        self._running = threading.Event()
        self._connected = threading.Event()

        self._rx_thread: Optional[threading.Thread] = None
        self._tx_thread: Optional[threading.Thread] = None

        self._tx_queue: "queue.Queue[bytes]" = queue.Queue(
            maxsize=self._config.tx_queue_size
        )

        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """
        Start RX/TX threads and establish a KISS connection.
        """
        if self._running.is_set():
            LOG.warning("KISSClient %s already running", self._name)
            return

        self._running.set()

        self._rx_thread = threading.Thread(
            target=self._rx_loop,
            name=f"{self._name}-rx",
            daemon=True,
        )
        self._tx_thread = threading.Thread(
            target=self._tx_loop,
            name=f"{self._name}-tx",
            daemon=True,
        )

        self._rx_thread.start()
        self._tx_thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """
        Stop RX/TX threads and close the underlying KISS connection.
        """
        if not self._running.is_set():
            return

        self._running.clear()

        # Wake TX thread so it can exit
        try:
            self._tx_queue.put_nowait(b"")
        except queue.Full:
            LOG.warning("TX queue full while stopping; forcing shutdown")

        if self._rx_thread is not None:
            self._rx_thread.join(timeout=timeout)
        if self._tx_thread is not None:
            self._tx_thread.join(timeout=timeout)

        with self._lock:
            if self._kiss_iface is not None:
                if hasattr(self._kiss_iface, "stop"):
                    try:
                        self._kiss_iface.stop()
                    except OSError:
                        LOG.warning("Error stopping KISS interface", exc_info=True)
                self._kiss_iface = None
                self._connected.clear()

    def send(self, frame: bytes, block: bool = True, timeout: Optional[float] = None):
        """
        Queue a raw AX.25 frame (already encoded) to be sent via KISS.

        `frame` should be the AX.25 frame payload; the kiss3 library handles
        KISS wrapping on write().
        """
        if not self._running.is_set():
            raise KISSClientError("Cannot send: client is not running")

        try:
            self._tx_queue.put(frame, block=block, timeout=timeout)
        except queue.Full as put_error:
            raise KISSClientError("TX queue is full") from put_error

    def is_connected(self) -> bool:
        return self._connected.is_set()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _create_kiss_iface(self):
        """
        Instantiate the appropriate KISS object (Serial or TCP).
        """
        if self._config.transport is TransportType.SERIAL:
            LOG.info(
                "Using SerialKISS on %s @ %d baud",
                self._config.serial_port,
                self._config.serial_baud,
            )
            serial_iface: SerialKISS = SerialKISS(
                self._config.serial_port,
                str(self._config.serial_baud),
            )
            return serial_iface

        if self._config.transport is TransportType.TCP:
            LOG.info(
                "Using TCPKISS to %s:%d",
                self._config.tcp_host,
                self._config.tcp_port,
            )
            tcp_iface: TCPKISS = TCPKISS(
                host=self._config.tcp_host,
                port=self._config.tcp_port,
            )
            return tcp_iface

        raise KISSClientError(f"Unsupported transport: {self._config.transport}")

    def _connect_with_backoff(self) -> None:
        """
        Ensure there is a working KISS connection, with backoff on failure.
        """
        delay = self._config.reconnect_base_delay

        while self._running.is_set() and not self._connected.is_set():
            try:
                with self._lock:
                    self._kiss_iface = self._create_kiss_iface()
                    self._kiss_iface.start()
                self._connected.set()
                LOG.info("KISS connection established")
            except OSError:
                self._connected.clear()
                LOG.warning(
                    "KISS connection failed; retrying in %.1f s",
                    delay,
                    exc_info=True,
                )
                time.sleep(delay)
                if delay < self._config.reconnect_max_delay:
                    delay *= 2.0

    # ------------------------------------------------------------------
    # RX / TX loops
    # ------------------------------------------------------------------

    def _rx_loop(self) -> None:
        """
        Receive loop: ensures connection, then delegates to kiss.read().
        """
        while self._running.is_set():
            if (not self._connected.is_set()) or (self._kiss_iface is None):
                self._connect_with_backoff()
                if (not self._connected.is_set()) or (self._kiss_iface is None):
                    time.sleep(1.0)
                    continue

            def _rx_callback_wrapper(frame: bytes) -> None:
                self._handle_rx_frame(frame)

            try:
                with self._lock:
                    if self._kiss_iface is None:
                        self._connected.clear()
                        continue
                    self._kiss_iface.read(callback=_rx_callback_wrapper)
            except OSError:
                LOG.warning("RX loop lost connection; reconnecting", exc_info=True)
                with self._lock:
                    self._kiss_iface = None
                    self._connected.clear()
                time.sleep(1.0)

    def _tx_loop(self) -> None:
        """
        Transmit loop: pulls frames off the queue and writes them via KISS.
        """
        while self._running.is_set():
            try:
                frame = self._tx_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            if not self._running.is_set():
                break
            if frame == b"":
                continue

            if (not self._connected.is_set()) or (self._kiss_iface is None):
                self._connect_with_backoff()
                if (not self._connected.is_set()) or (self._kiss_iface is None):
                    LOG.warning("Dropping TX frame: no KISS connection available")
                    continue

            try:
                with self._lock:
                    iface = self._kiss_iface
                    if iface is None:
                        raise KISSClientError("KISS interface missing in TX loop")
                    iface.write(frame)
            except OSError:
                LOG.warning(
                    "Error writing frame; dropping connection and retrying",
                    exc_info=True,
                )
                with self._lock:
                    self._kiss_iface = None
                    self._connected.clear()
                time.sleep(1.0)

    # ------------------------------------------------------------------
    # RX callback wrapper
    # ------------------------------------------------------------------

    def _handle_rx_frame(self, frame: bytes) -> None:
        """
        Wrapper around user callback to keep RX loop safe.
        """
        try:
            self._rx_callback(frame)
        except ValueError:
            LOG.warning("Value error in RX callback; frame dropped", exc_info=True)
