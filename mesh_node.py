"""
Mesh node implementation:

- Uses KISSClient for link-layer access.
- Implements a BATMAN-lite style routing (OGMs).
- Maintains routing + neighbor tables.
- Deduplicates DATA frames using full packet-ID cache (Option C).
- Compresses payloads with zlib.
- Optional AES-GCM encryption.
- No broad exceptions, no top-level execution.
"""

from __future__ import annotations

import logging
import struct
import threading
import time
import zlib
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, Callable

from mesh_config import MeshNodeConfig
from kiss_link import KISSClient
from crypto_layer import MeshEncryptor

LOG = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------

MESH_VERSION = 1

MESH_MSG_DATA = 0
MESH_MSG_OGM = 1

MESH_FLAG_COMPRESSED = 0x01
MESH_FLAG_ENCRYPTED = 0x02


# ----------------------------------------------------------------------
# Routing State Structures
# ----------------------------------------------------------------------

@dataclass
class OriginatorEntry:
    best_next_hop: bytes
    last_seqno: int
    metric: int
    last_seen: float


@dataclass
class NeighborEntry:
    last_seen: float
    link_metric: int


@dataclass
class MeshRoutingState:
    originators: Dict[bytes, OriginatorEntry] = field(default_factory=dict)
    neighbors: Dict[bytes, NeighborEntry] = field(default_factory=dict)


# ----------------------------------------------------------------------
# Mesh Node
# ----------------------------------------------------------------------

class MeshNode:
    """
    Full mesh node for AX.25-over-KISS VHF routing.

    Behaviors:
    - Periodic OGM generation
    - Neighbor/route tracking
    - DATA forwarding
    - Compression
    - Optional encryption
    - PACKET-ID CACHE DEDUP (Option C)
    """

    def __init__(
            self,
            config: MeshNodeConfig,
            kiss_client_factory: Callable[[Callable[[bytes], None]], KISSClient],
            app_data_callback: Optional[
                Callable[[bytes, bytes, int, bytes], None]
            ] = None,
    ) -> None:
        self._config = config
        self._node_id = self._derive_node_id(config.callsign)
        self._mesh_dest = config.mesh_dest_callsign.encode("ascii")
        self._routing_state = MeshRoutingState()
        self._encryptor = MeshEncryptor(config.security_config)
        self._kiss_client = kiss_client_factory(self._on_kiss_frame)

        # Application-level delivery callback
        # signature: (origin_id, dest_id, data_seqno, payload_bytes)
        self._app_data_callback = app_data_callback

        # Seqno generator lock
        self._seqno_lock = threading.Lock()
        self._seqno = 0

        # OPTION C: full packet-ID dedup
        self._data_seen: Dict[Tuple[bytes, int], float] = {}
        self._data_seen_lock = threading.Lock()
        self._data_seen_expiry = self._config.routing_config.data_seen_expiry_seconds

        self._running = threading.Event()

        self._ogm_thread: Optional[threading.Thread] = None
        self._cleanup_thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """
        Start the mesh node: KISS client + routing threads.
        """
        if self._running.is_set():
            LOG.warning("MeshNode already running")
            return

        self._running.set()

        self._kiss_client.start()

        self._ogm_thread = threading.Thread(
            target=self._ogm_loop,
            name="mesh-ogm-loop",
            daemon=True,
        )
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            name="mesh-cleanup-loop",
            daemon=True,
        )
        self._ogm_thread.start()
        self._cleanup_thread.start()

    def stop(self) -> None:
        """
        Stop routing threads and underlying KISS client.
        """
        if not self._running.is_set():
            return

        self._running.clear()
        self._kiss_client.stop()

        if self._ogm_thread is not None:
            self._ogm_thread.join(timeout=5.0)
        if self._cleanup_thread is not None:
            self._cleanup_thread.join(timeout=5.0)

    def send_application_data(self, dest_node_id: bytes, payload: bytes) -> None:
        """
        Send application-level data to a destination node ID (8 bytes).
        """
        if len(dest_node_id) != 8:
            raise ValueError("dest_node_id must be exactly 8 bytes")

        seqno = self._next_seqno()
        mesh_payload = self._build_data_payload(dest_node_id, seqno, payload)
        frame = self._wrap_in_ax25_ui(mesh_payload)
        self._kiss_client.send(frame)

    # ------------------------------------------------------------------
    # ID / Seqno Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _derive_node_id(callsign: str) -> bytes:
        encoded = callsign.encode("ascii", errors="ignore")
        return encoded.ljust(8, b"\x00")[:8]

    def _next_seqno(self) -> int:
        with self._seqno_lock:
            self._seqno = (self._seqno + 1) & 0xFFFFFFFF
            return self._seqno

    # ------------------------------------------------------------------
    # Minimal AX.25 UI Frame Builder
    # ------------------------------------------------------------------

    @staticmethod
    def _encode_ax25_address(callsign: str, last: bool = False) -> bytes:
        """
        Encode callsign[-ssid] into 7-byte AX.25 format.
        """
        if "-" in callsign:
            base, ssid_str = callsign.split("-", 1)
            try:
                ssid_value = int(ssid_str)
            except ValueError:
                ssid_value = 0
        else:
            base = callsign
            ssid_value = 0

        base = base.upper()[:6]
        call_bytes = base.encode("ascii").ljust(6, b" ")

        shifted = bytearray(7)
        for idx, b in enumerate(call_bytes):
            shifted[idx] = b << 1

        ssid_field = 0x60 | ((ssid_value & 0x0F) << 1)
        if last:
            ssid_field |= 0x01

        shifted[6] = ssid_field
        return bytes(shifted)

    def _wrap_in_ax25_ui(self, info_payload: bytes) -> bytes:
        dest = self._encode_ax25_address(self._config.mesh_dest_callsign)
        src = self._encode_ax25_address(self._config.callsign, last=True)
        control = b"\x03"
        pid = b"\xf0"
        return dest + src + control + pid + info_payload

    # ------------------------------------------------------------------
    # Mesh Header Encode/Decode
    # ------------------------------------------------------------------

    @staticmethod
    def _build_mesh_header(
            msg_type: int,
            flags: int,
            ttl: int,
            origin_id: bytes,
            seqno: int,
    ) -> bytes:
        header = bytearray(16)
        header[0] = MESH_VERSION
        header[1] = msg_type
        header[2] = flags
        header[3] = ttl
        header[4:12] = origin_id
        header[12:16] = struct.pack(">I", seqno)
        return bytes(header)

    @staticmethod
    def _parse_mesh_header(info: bytes) -> Tuple[int, int, int, int, bytes, int]:
        if len(info) < 16:
            raise ValueError("info too short for mesh header")
        version = info[0]
        msg_type = info[1]
        flags = info[2]
        ttl = info[3]
        origin_id = info[4:12]
        seqno = struct.unpack(">I", info[12:16])[0]
        return version, msg_type, flags, ttl, origin_id, seqno

    # ------------------------------------------------------------------
    # OGM Construction & Handling
    # ------------------------------------------------------------------

    def _build_ogm_payload(self) -> bytes:
        seqno = self._next_seqno()
        ttl = self._config.routing_config.ogm_ttl

        mesh_header = self._build_mesh_header(
            msg_type=MESH_MSG_OGM,
            flags=0,
            ttl=ttl,
            origin_id=self._node_id,
            seqno=seqno,
        )

        prev_hop = self._node_id
        link_metric = 255

        body = prev_hop + bytes([link_metric])
        return mesh_header + body

    def _handle_ogm(
            self,
            origin_id: bytes,
            seqno: int,
            ttl: int,
            prev_hop_id: bytes,
            link_metric: int,
    ) -> None:
        now = time.time()

        # Update neighbors
        nei = self._routing_state.neighbors.get(prev_hop_id)
        if nei is None:
            self._routing_state.neighbors[prev_hop_id] = NeighborEntry(
                last_seen=now,
                link_metric=link_metric,
            )
        else:
            nei.last_seen = now
            nei.link_metric = link_metric

        # Update originators
        entry = self._routing_state.originators.get(origin_id)
        if entry is None:
            self._routing_state.originators[origin_id] = OriginatorEntry(
                best_next_hop=prev_hop_id,
                last_seqno=seqno,
                metric=link_metric,
                last_seen=now,
            )
        else:
            if seqno > entry.last_seqno:
                entry.best_next_hop = prev_hop_id
                entry.last_seqno = seqno
                entry.metric = link_metric
                entry.last_seen = now

        if ttl > 1:
            fwd_ttl = ttl - 1
            mesh_header = self._build_mesh_header(
                msg_type=MESH_MSG_OGM,
                flags=0,
                ttl=fwd_ttl,
                origin_id=origin_id,
                seqno=seqno,
            )
            fwd_body = self._node_id + bytes([link_metric])
            fwd_payload = mesh_header + fwd_body
            frame = self._wrap_in_ax25_ui(fwd_payload)
            self._kiss_client.send(frame)

    # ------------------------------------------------------------------
    # DATA Construction & Handling
    # ------------------------------------------------------------------

    def _build_data_payload(
            self,
            dest_id: bytes,
            data_seqno: int,
            app_payload: bytes,
    ) -> bytes:
        flags = 0

        compressed = zlib.compress(app_payload)
        if len(compressed) < len(app_payload):
            payload_to_send = compressed
            flags |= MESH_FLAG_COMPRESSED
        else:
            payload_to_send = app_payload

        associated_data = self._node_id + dest_id + struct.pack(">I", data_seqno)

        if self._encryptor.encryption_enabled:
            nonce, ciphertext = self._encryptor.encrypt(
                payload_to_send,
                associated_data,
            )
            flags |= MESH_FLAG_ENCRYPTED
            body = dest_id + struct.pack(">I", data_seqno) + nonce + ciphertext
        else:
            body = dest_id + struct.pack(">I", data_seqno) + payload_to_send

        ttl = self._config.routing_config.ogm_ttl
        mesh_header = self._build_mesh_header(
            msg_type=MESH_MSG_DATA,
            flags=flags,
            ttl=ttl,
            origin_id=self._node_id,
            seqno=data_seqno,
        )

        return mesh_header + body

    def _handle_data_frame(
            self,
            origin_id: bytes,
            seqno: int,
            ttl: int,
            flags: int,
            body: bytes,
    ) -> None:

        # ----------------------------------------------------------
        # OPTION C: PACKET-ID DEDUP
        # ----------------------------------------------------------
        now = time.time()
        key = (origin_id, seqno)

        with self._data_seen_lock:
            if key in self._data_seen:
                return  # duplicate — drop
            self._data_seen[key] = now

        # ----------------------------------------------------------
        # Continue parsing
        # ----------------------------------------------------------
        if len(body) < 12:
            return

        dest_id = body[0:8]
        data_seq = struct.unpack(">I", body[8:12])[0]
        remainder = body[12:]

        associated_data = origin_id + dest_id + struct.pack(">I", data_seq)

        if (flags & MESH_FLAG_ENCRYPTED) != 0:
            if len(remainder) < 13:
                return
            nonce = remainder[0:12]
            ciphertext = remainder[12:]
            decrypted = self._encryptor.decrypt(nonce, ciphertext, associated_data)
            app_bytes = decrypted
        else:
            app_bytes = remainder

        if (flags & MESH_FLAG_COMPRESSED) != 0:
            try:
                app_bytes = zlib.decompress(app_bytes)
            except zlib.error:
                LOG.warning("Failed to decompress payload; dropping DATA")
                return

        # ------------------------------------------------------
        # Delivery or forwarding
        # ------------------------------------------------------

        if dest_id == self._node_id:
            if self._app_data_callback is not None:
                self._app_data_callback(origin_id, dest_id, data_seq, app_bytes)
            else:
                LOG.info(
                    "DATA delivered from origin %s seq %d: %r",
                    origin_id,
                    data_seq,
                    app_bytes,
                )
            return

        # Forward
        if ttl <= 1:
            return

        next_hop = self._lookup_best_next_hop(dest_id)
        if next_hop is None:
            return

        fwd_ttl = ttl - 1
        mesh_header = self._build_mesh_header(
            msg_type=MESH_MSG_DATA,
            flags=flags,
            ttl=fwd_ttl,
            origin_id=origin_id,
            seqno=seqno,
        )

        fwd_payload = mesh_header + body
        frame = self._wrap_in_ax25_ui(fwd_payload)
        self._kiss_client.send(frame)

    def _lookup_best_next_hop(self, dest_id: bytes) -> Optional[bytes]:
        entry = self._routing_state.originators.get(dest_id)
        if entry is None:
            return None
        return entry.best_next_hop

    # ------------------------------------------------------------------
    # Background Threads
    # ------------------------------------------------------------------

    def _ogm_loop(self) -> None:
        interval = self._config.routing_config.ogm_interval_seconds
        while self._running.is_set():
            payload = self._build_ogm_payload()
            frame = self._wrap_in_ax25_ui(payload)
            self._kiss_client.send(frame)
            time.sleep(interval)

    def _cleanup_loop(self) -> None:
        route_exp = self._config.routing_config.route_expiry_seconds
        neigh_exp = self._config.routing_config.neighbor_expiry_seconds

        while self._running.is_set():
            now = time.time()

            # Originators cleanup
            dead_orig = [
                key
                for key, entry in self._routing_state.originators.items()
                if now - entry.last_seen > route_exp
            ]
            for key in dead_orig:
                del self._routing_state.originators[key]

            # Neighbors cleanup
            dead_nei = [
                key
                for key, entry in self._routing_state.neighbors.items()
                if now - entry.last_seen > neigh_exp
            ]
            for key in dead_nei:
                del self._routing_state.neighbors[key]

            # DATA dedup cache cleanup
            dead_data = [
                key
                for key, ts in self._data_seen.items()
                if now - ts > self._data_seen_expiry
            ]
            with self._data_seen_lock:
                for key in dead_data:
                    del self._data_seen[key]

            time.sleep(5.0)

    # ------------------------------------------------------------------
    # KISS RX
    # ------------------------------------------------------------------

    def _on_kiss_frame(self, frame: bytes) -> None:
        """
        Parse AX.25 UI frame → extract mesh header → handle message.
        """

        if len(frame) <= 16:
            return

        info_start = self._find_info_start(frame)
        if info_start is None:
            return

        info = frame[info_start:]

        try:
            version, msg_type, flags, ttl, origin_id, seqno = self._parse_mesh_header(info)
        except ValueError:
            return

        if version != MESH_VERSION:
            return

        body = info[16:]

        if msg_type == MESH_MSG_OGM:
            if len(body) < 9:
                return
            prev_hop = body[0:8]
            link_metric = body[8]
            self._handle_ogm(origin_id, seqno, ttl, prev_hop, link_metric)
        elif msg_type == MESH_MSG_DATA:
            self._handle_data_frame(origin_id, seqno, ttl, flags, body)

    @staticmethod
    def _find_info_start(frame: bytes) -> Optional[int]:
        if len(frame) <= 16:
            return None
        return 16
