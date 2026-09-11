#!/usr/bin/env python3

import argparse
import ipaddress
import logging
import os
import signal
import socket
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import ifaddr
import yaml
from zeroconf import ServiceInfo, Zeroconf

SERVICE_TYPE = "_local-ai._tcp.local."


@dataclass(frozen=True)
class Config:
    name: str
    port: int
    api: str
    auth: str
    base_path: str
    models_path: str


def load_config(
    path: Path | None = None, environ: Mapping[str, str] | None = None
) -> Config:
    raw = {}
    if path:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ValueError("config root must be a mapping")

    service = raw.get("service", {})
    api = raw.get("api", {})
    if not isinstance(service, dict) or not isinstance(api, dict):
        raise ValueError("service and api config sections must be mappings")

    env = os.environ if environ is None else environ
    values = {
        "name": service.get("name", short_hostname()),
        "port": api.get("port", 11434),
        "api": api.get("type", "openai"),
        "auth": api.get("auth", "none"),
        "base_path": api.get("base_path", "/v1"),
        "models_path": api.get("models_path", "/v1/models"),
    }
    for env_name, key in {
        "LOCAL_AI_NAME": "name",
        "LOCAL_AI_PORT": "port",
        "LOCAL_AI_API": "api",
        "LOCAL_AI_AUTH": "auth",
        "LOCAL_AI_BASE_PATH": "base_path",
        "LOCAL_AI_MODELS_PATH": "models_path",
    }.items():
        if env_name in env:
            values[key] = env[env_name]

    try:
        port = int(values["port"])
    except (TypeError, ValueError) as error:
        raise ValueError("port must be an integer") from error

    config = Config(
        name=str(values["name"]).strip(),
        port=port,
        api=str(values["api"]).strip(),
        auth=str(values["auth"]).strip(),
        base_path=str(values["base_path"]).strip(),
        models_path=str(values["models_path"]).strip(),
    )
    validate_config(config)
    return config


def validate_config(config: Config) -> None:
    if not config.name or len(config.name.encode("utf-8")) > 63:
        raise ValueError("service name must contain 1 to 63 UTF-8 bytes")
    if not 1 <= config.port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    if not config.api:
        raise ValueError("api type must not be empty")
    if config.auth not in {"none", "api-key"}:
        raise ValueError("auth must be none or api-key")
    if not config.base_path.startswith("/") or not config.models_path.startswith("/"):
        raise ValueError("base_path and models_path must start with /")
    for key, value in {
        "api": config.api,
        "auth": config.auth,
        "base": config.base_path,
        "models": config.models_path,
    }.items():
        if len(f"{key}={value}".encode("utf-8")) > 255:
            raise ValueError(f"TXT record {key} exceeds 255 bytes")


def short_hostname() -> str:
    hostname = socket.gethostname().rstrip(".")
    if hostname.lower().endswith(".local"):
        hostname = hostname[:-6]
    return hostname.split(".", 1)[0]


def discover_addresses() -> list[str]:
    addresses = {
        str(address)
        for adapter in ifaddr.get_adapters()
        for adapter_ip in adapter.ips
        for address in [
            ipaddress.ip_address(
                adapter_ip.ip[0] if isinstance(adapter_ip.ip, tuple) else adapter_ip.ip
            )
        ]
        if not address.is_loopback and not address.is_unspecified
    }
    if not addresses:
        raise RuntimeError("no non-loopback network address found")
    return sorted(
        addresses,
        key=lambda address: (ipaddress.ip_address(address).version, address),
    )


def build_service_info(
    config: Config, hostname: str, addresses: list[str]
) -> ServiceInfo:
    return ServiceInfo(
        SERVICE_TYPE,
        f"{config.name}.{SERVICE_TYPE}",
        parsed_addresses=addresses,
        port=config.port,
        properties={
            "v": "1",
            "api": config.api,
            "auth": config.auth,
            "base": config.base_path,
            "models": config.models_path,
        },
        server=f"{hostname}.local.",
    )


def run(config: Config, stop_event: threading.Event) -> None:
    hostname = short_hostname()
    info = build_service_info(config, hostname, discover_addresses())
    zeroconf = Zeroconf()
    registered = False
    try:
        zeroconf.register_service(info)
        registered = True
        logging.info("Local AI Discovery started")
        logging.info("Service: %s", info.name)
        logging.info("Host: %s", info.server)
        logging.info("Port: %s", config.port)
        logging.info("API: %s", config.api)
        logging.info("Auth: %s", config.auth)
        logging.info("Base Path: %s", config.base_path)
        logging.info("Models Path: %s", config.models_path)
        stop_event.wait()
    finally:
        if registered:
            logging.info("Unregistering Local AI service...")
            try:
                zeroconf.unregister_service(info)
            finally:
                zeroconf.close()
            logging.info("Local AI Discovery stopped")
        else:
            zeroconf.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Advertise a local AI API over mDNS")
    parser.add_argument("--config", type=Path, help="YAML config file")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    stop_event = threading.Event()
    for stop_signal in (signal.SIGINT, signal.SIGTERM):
        signal.signal(stop_signal, lambda _signum, _frame: stop_event.set())
    run(load_config(args.config), stop_event)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
