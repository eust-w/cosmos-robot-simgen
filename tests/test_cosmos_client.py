import base64
import json
import tempfile
import unittest
from pathlib import Path

from cosmos_robot_simgen.cosmos import Cosmos3NanoClient, CosmosClientError, write_cosmos_artifacts


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class CosmosClientTests(unittest.TestCase):
    def test_generate_video_decodes_b64_video_and_sends_payload(self):
        calls = []

        def opener(request, timeout):
            calls.append((request, timeout))
            return FakeResponse({"b64_video": base64.b64encode(b"mp4-bytes").decode("ascii"), "id": "abc"})

        client = Cosmos3NanoClient("http://example.test/v1/infer", api_key="token", opener=opener)
        generation = client.generate_video("robot moves", seed=7, num_output_frames=12)

        self.assertEqual(generation.video_bytes, b"mp4-bytes")
        self.assertEqual(generation.request_payload["seed"], 7)
        self.assertEqual(generation.response_metadata["id"], "abc")
        self.assertEqual(calls[0][0].headers["Authorization"], "Bearer token")

    def test_missing_b64_video_is_error(self):
        client = Cosmos3NanoClient("http://example.test/v1/infer", opener=lambda request, timeout: FakeResponse({}))

        with self.assertRaises(CosmosClientError):
            client.generate_video("robot moves")

    def test_write_cosmos_artifacts_writes_video_and_metadata(self):
        generation = Cosmos3NanoClient(
            "http://example.test/v1/infer",
            opener=lambda request, timeout: FakeResponse({"b64_video": base64.b64encode(b"video").decode("ascii")}),
        ).generate_video("robot")

        with tempfile.TemporaryDirectory() as tmp:
            artifacts = write_cosmos_artifacts(Path(tmp), generation)

            self.assertTrue((Path(tmp) / artifacts["video"]).exists())
            self.assertTrue((Path(tmp) / artifacts["request"]).exists())
            self.assertEqual(artifacts["video_bytes"], 5)


if __name__ == "__main__":
    unittest.main()
