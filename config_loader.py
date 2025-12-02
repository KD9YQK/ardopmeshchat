# config_loader.py

from __future__ import annotations

from typing import Dict, Any
import binascii

import yaml  # pip install pyyaml

from mesh_config import (
    TransportType,
    KISSConnectionConfig,
    MeshRoutingConfig,
    MeshSecurityConfig,
    MeshNodeConfig,
)
from chat_client import MeshChatConfig, ChatPeer  # if you're using chat


def _get_required(mapping: Dict[str, Any], key: str) -> Any:
    if key not in mapping:
        raise KeyError(f"Missing required config key: {key}")
    return mapping[key]


def _load_transport(cfg: Dict[str, Any]) -> TransportType:
    value = cfg.get("transport", "tcp").lower()
    if value == "tcp":
        return TransportType.TCP
    if value == "serial":
        return TransportType.SERIAL
    raise ValueError(f"Unknown transport type: {value}")


def load_kiss_config(root: Dict[str, Any]) -> KISSConnectionConfig:
    kiss_cfg = root.get("kiss", {})
    transport = _load_transport(kiss_cfg)

    serial_port = kiss_cfg.get("serial_port", "/dev/ttyUSB0")
    serial_baud = int(kiss_cfg.get("serial_baud", 1200))

    tcp_host = kiss_cfg.get("tcp_host", "127.0.0.1")
    tcp_port = int(kiss_cfg.get("tcp_port", 8001))

    reconnect_base_delay = float(kiss_cfg.get("reconnect_base_delay", 5.0))
    reconnect_max_delay = float(kiss_cfg.get("reconnect_max_delay", 60.0))
    tx_queue_size = int(kiss_cfg.get("tx_queue_size", 1000))

    return KISSConnectionConfig(
        transport=transport,
        serial_port=serial_port,
        serial_baud=serial_baud,
        tcp_host=tcp_host,
        tcp_port=tcp_port,
        reconnect_base_delay=reconnect_base_delay,
        reconnect_max_delay=reconnect_max_delay,
        tx_queue_size=tx_queue_size,
    )


def load_routing_config(root: Dict[str, Any]) -> MeshRoutingConfig:
    routing_cfg = root.get("routing", {})

    ogm_interval = float(routing_cfg.get("ogm_interval_seconds", 10.0))
    ogm_ttl = int(routing_cfg.get("ogm_ttl", 5))
    route_expiry = float(routing_cfg.get("route_expiry_seconds", 120.0))
    neighbor_expiry = float(routing_cfg.get("neighbor_expiry_seconds", 60.0))
    data_seen_expiry = float(routing_cfg.get("data_seen_expiry_seconds", 30.0))

    return MeshRoutingConfig(
        ogm_interval_seconds=ogm_interval,
        ogm_ttl=ogm_ttl,
        route_expiry_seconds=route_expiry,
        neighbor_expiry_seconds=neighbor_expiry,
        data_seen_expiry_seconds=data_seen_expiry,  # you'll add this field
    )


def load_security_config(root: Dict[str, Any]) -> MeshSecurityConfig:
    sec_cfg = root.get("security", {})

    enable_encryption = bool(sec_cfg.get("enable_encryption", False))
    key_hex = sec_cfg.get("key_hex")
    key_bytes = None
    if key_hex is not None:
        key_bytes = binascii.unhexlify(key_hex)

    return MeshSecurityConfig(
        enable_encryption=enable_encryption,
        key=key_bytes,
    )


def load_mesh_node_config(root: Dict[str, Any]) -> MeshNodeConfig:
    mesh_cfg = root.get("mesh", {})

    callsign = str(_get_required(mesh_cfg, "callsign"))
    mesh_dest_callsign = str(mesh_cfg.get("mesh_dest_callsign", "QMESH-0"))

    kiss_cfg = load_kiss_config(root)
    routing_cfg = load_routing_config(root)
    security_cfg = load_security_config(root)

    return MeshNodeConfig(
        callsign=callsign,
        mesh_dest_callsign=mesh_dest_callsign,
        kiss_config=kiss_cfg,
        routing_config=routing_cfg,
        security_config=security_cfg,
    )


def load_chat_config_from_yaml(path: str) -> MeshChatConfig:
    """
    Load complete MeshChatConfig (MeshNodeConfig + chat) from YAML file.
    """
    with open(path, "r", encoding="utf-8") as f:
        root = yaml.safe_load(f)

    if not isinstance(root, dict):
        raise ValueError("Top-level YAML must be a mapping")

    mesh_node_cfg = load_mesh_node_config(root)

    chat_cfg_raw = root.get("chat", {})
    db_path = str(_get_required(chat_cfg_raw, "db_path"))

    peers_raw = chat_cfg_raw.get("peers", {})
    peers: Dict[str, ChatPeer] = {}

    for nickname, peer_data_any in peers_raw.items():
        if not isinstance(peer_data_any, dict):
            continue
        node_id_hex = _get_required(peer_data_any, "node_id_hex")
        peer_nick = str(peer_data_any.get("nick", nickname))

        node_id_bytes = binascii.unhexlify(node_id_hex)
        if len(node_id_bytes) != 8:
            raise ValueError(
                f"node_id_hex for peer {nickname} must decode to 8 bytes"
            )

        peers[nickname] = ChatPeer(
            node_id=node_id_bytes,
            nick=peer_nick,
        )

    return MeshChatConfig(
        mesh_node_config=mesh_node_cfg,
        db_path=db_path,
        peers=peers,
    )
