import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from local_ai_discovery import Config, build_service_info, load_config, run


class LocalAiDiscoveryTest(unittest.TestCase):
    def test_config_file_with_environment_override(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory, "config.yaml")
            path.write_text(
                "service:\n  name: DGX-Spark-01\napi:\n  port: 11434\n  type: openai\n"
                "  auth: none\n  base_path: /v1\n  models_path: /v1/models\n",
                encoding="utf-8",
            )
            config = load_config(
                path, {"LOCAL_AI_PORT": "8000", "LOCAL_AI_AUTH": "api-key"}
            )

        self.assertEqual(config.name, "DGX-Spark-01")
        self.assertEqual(config.port, 8000)
        self.assertEqual(config.auth, "api-key")

    def test_rejects_unknown_auth_method(self) -> None:
        with self.assertRaisesRegex(ValueError, "auth must be none or api-key"):
            load_config(environ={"LOCAL_AI_AUTH": "password"})

    def test_service_info_matches_protocol(self) -> None:
        config = Config(
            "DGX-Spark-01", 11434, "openai", "none", "/v1", "/v1/models"
        )
        info = build_service_info(config, "dgx-spark-01", ["192.168.1.50"])

        self.assertEqual(info.name, "DGX-Spark-01._local-ai._tcp.local.")
        self.assertEqual(info.server, "dgx-spark-01.local.")
        self.assertEqual(info.port, 11434)
        self.assertEqual(
            info.decoded_properties,
            {
                "v": "1",
                "api": "openai",
                "auth": "none",
                "base": "/v1",
                "models": "/v1/models",
            },
        )

    @patch("local_ai_discovery.discover_addresses", return_value=["192.168.1.50"])
    @patch("local_ai_discovery.Zeroconf")
    def test_run_unregisters_and_closes(
        self, zeroconf_class: Mock, _addresses: Mock
    ) -> None:
        stop_event = threading.Event()
        stop_event.set()
        config = Config(
            "DGX-Spark-01", 11434, "openai", "none", "/v1", "/v1/models"
        )

        run(config, stop_event)

        zeroconf = zeroconf_class.return_value
        zeroconf.register_service.assert_called_once()
        zeroconf.unregister_service.assert_called_once()
        zeroconf.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
