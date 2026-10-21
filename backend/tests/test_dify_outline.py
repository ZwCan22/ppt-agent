"""Test our Dify adapter against fixed responses, without any real services."""

import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

import app
import httpx
from pydantic import SecretStr

from app.schemas.ppt import PptBrief


def load_isolated_client():
    """Use the real client code with fake settings; never load the real .env.

    The temporary module substitution is undone after loading. Other tests can
    still import the application's normal configuration independently.
    """
    config = ModuleType("app.core.config")
    config.settings = SimpleNamespace(
        dify_base_url="http://dify.test/v1",
        dify_api_key=SecretStr("app-unit-test-only"),
        dify_timeout_seconds=180,
    )
    source = Path(app.__file__).parent / "clients" / "dify.py"
    spec = importlib.util.spec_from_file_location("_dify_outline_under_test", source)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"app.core.config": config}):
        spec.loader.exec_module(module)
    return module


def successful_response(page_count=6):
    """Build a fresh response per test, so test changes cannot affect others."""
    return {
        "workflow_run_id": "9d5f9bb4-c59c-4cce-ad31-6660ee6dda3d",
        "data": {
            "status": "succeeded",
            "outputs": {
                "outline": {
                    "slides": [
                        {"kind": "cover", "title": "Cover", "bullets": []},
                        *[
                            {"kind": "content", "title": f"Part {number}", "bullets": ["A point"]}
                            for number in range(1, page_count - 1)
                        ],
                        {"kind": "closing", "title": "Thank you", "bullets": []},
                    ]
                }
            },
        },
    }


class DifyOutlineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = load_isolated_client()

    def setUp(self):
        self.brief = PptBrief(topic="Test topic", audience="Test audience", slide_count=6)

    def generate(self, response=None, *, raw_text=None):
        """Only the external HTTP response is replaced; adapter logic is real."""
        real_httpx_client = httpx.Client

        def handle_request(request):
            self.last_request = request
            if raw_text is not None:
                return httpx.Response(200, text=raw_text)
            return httpx.Response(200, json=response)

        transport = httpx.MockTransport(handle_request)

        def make_client(**kwargs):
            return real_httpx_client(transport=transport, **kwargs)

        with patch.object(self.client.httpx, "Client", side_effect=make_client):
            return self.client.generate_outline(self.brief, user_id="unit-test-user")

    def test_valid_six_page_outline_is_accepted(self):
        # Arrange: user requests six pages; Dify returns a valid six-page outline.
        response = successful_response(6)

        # Act: call our real adapter.
        outline = self.generate(response)

        # Assert: result and outgoing request satisfy the integration contract.
        self.assertEqual(len(outline.slides), 6)
        request_body = json.loads(self.last_request.content)
        self.assertEqual(request_body["inputs"]["slide_count"], "6")
        self.assertEqual(request_body["inputs"]["topic"], self.brief.topic)
        self.assertEqual(request_body["response_mode"], "blocking")
        self.assertEqual(self.last_request.url.path, "/v1/workflows/run")

    def test_seven_pages_are_rejected_when_six_were_requested(self):
        response = successful_response(7)

        with self.assertRaises(self.client.DifyOutlineError) as caught:
            self.generate(response)

        self.assertEqual(caught.exception.code, "DIFY_OUTLINE_INVALID")

    def test_valid_slide_types_in_wrong_positions_are_rejected(self):
        for index, wrong_kind in ((0, "content"), (2, "cover"), (5, "content")):
            with self.subTest(index=index, wrong_kind=wrong_kind):
                response = successful_response()
                response["data"]["outputs"]["outline"]["slides"][index]["kind"] = wrong_kind

                with self.assertRaises(self.client.DifyOutlineError) as caught:
                    self.generate(response)

                self.assertEqual(caught.exception.code, "DIFY_OUTLINE_INVALID")

    def test_http_200_with_failed_workflow_is_still_failure(self):
        response = successful_response()
        response["data"].update(status="failed", error="Model unavailable")

        with self.assertRaises(self.client.DifyOutlineError) as caught:
            self.generate(response)

        self.assertEqual(caught.exception.code, "DIFY_WORKFLOW_FAILED")
        self.assertEqual(caught.exception.run_id, response["workflow_run_id"])

    def test_broken_json_is_reported_as_invalid_response(self):
        with self.assertRaises(self.client.DifyOutlineError) as caught:
            self.generate(raw_text='{"data": {"status": "succeeded"')

        self.assertEqual(caught.exception.code, "DIFY_INVALID_RESPONSE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
