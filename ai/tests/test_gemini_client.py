import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mini_sorting_ai.gemini_client import AIServiceError, GeminiClient, MockClient  # noqa: E402

SECRET = "SECRET-KEY-VALUE"


def no_sleep(_):
    return None


class GeminiClientTests(unittest.TestCase):
    def test_missing_key_is_rejected_without_leaking(self):
        with self.assertRaises(AIServiceError) as ctx:
            GeminiClient(api_key="", model="m", _call=lambda m, p: "{}")
        self.assertEqual(ctx.exception.reason, "AI_NOT_CONFIGURED_KEY")

    def test_missing_model_is_rejected(self):
        with self.assertRaises(AIServiceError) as ctx:
            GeminiClient(api_key=SECRET, model=" ", _call=lambda m, p: "{}")
        self.assertEqual(ctx.exception.reason, "AI_NOT_CONFIGURED_MODEL")

    def test_success_returns_text_and_passes_model(self):
        seen = {}

        def fake(model, prompt):
            seen["model"], seen["prompt"] = model, prompt
            return '{"recipient_room": "202"}'

        c = GeminiClient(api_key=SECRET, model="model-x", _call=fake, _sleep=no_sleep)
        self.assertEqual(c.generate_json("hello"), '{"recipient_room": "202"}')
        self.assertEqual(seen, {"model": "model-x", "prompt": "hello"})

    def test_transient_failure_then_success(self):
        calls = []

        def flaky(model, prompt):
            calls.append(1)
            if len(calls) < 2:
                raise ConnectionError("network down")
            return "{}"

        c = GeminiClient(api_key=SECRET, model="m", max_retries=2, _call=flaky, _sleep=no_sleep)
        self.assertEqual(c.generate_json("p"), "{}")
        self.assertEqual(len(calls), 2)

    def test_persistent_failure_is_bounded_and_does_not_leak_key(self):
        calls = []

        def down(model, prompt):
            calls.append(1)
            raise ConnectionError(f"failed with key {SECRET}")

        c = GeminiClient(api_key=SECRET, model="m", max_retries=2, _call=down, _sleep=no_sleep)
        with self.assertRaises(AIServiceError) as ctx:
            c.generate_json("p")
        self.assertEqual(len(calls), 3)  # 1 ครั้ง + retry 2 ครั้ง
        self.assertEqual(ctx.exception.reason, "AI_UNAVAILABLE")
        self.assertNotIn(SECRET, str(ctx.exception))

    def test_empty_response_is_service_error(self):
        c = GeminiClient(api_key=SECRET, model="m", max_retries=0,
                         _call=lambda m, p: "   ", _sleep=no_sleep)
        with self.assertRaises(AIServiceError) as ctx:
            c.generate_json("p")
        self.assertEqual(ctx.exception.reason, "AI_EMPTY_RESPONSE")

    def test_negative_retries_rejected(self):
        with self.assertRaises(ValueError):
            GeminiClient(api_key=SECRET, model="m", max_retries=-1, _call=lambda m, p: "{}")

    def test_backoff_is_bounded(self):
        waits = []

        def down(model, prompt):
            raise ConnectionError("x")

        c = GeminiClient(api_key=SECRET, model="m", max_retries=2, backoff_s=0.5,
                         _call=down, _sleep=waits.append)
        with self.assertRaises(AIServiceError):
            c.generate_json("p")
        self.assertEqual(waits, [0.5, 1.0])


class MockClientTests(unittest.TestCase):
    def test_mock_identifies_itself(self):
        self.assertEqual(MockClient(response_text="{}").source, "mock")
        self.assertEqual(GeminiClient(api_key=SECRET, model="m",
                                      _call=lambda m, p: "{}").source, "gemini")

    def test_mock_returns_fixed_text_and_counts_calls(self):
        m = MockClient(response_text='{"a": 1}')
        self.assertEqual(m.generate_json("p"), '{"a": 1}')
        self.assertEqual(m.calls, 1)

    def test_mock_can_simulate_service_error(self):
        m = MockClient(error_reason="AI_UNAVAILABLE")
        with self.assertRaises(AIServiceError) as ctx:
            m.generate_json("p")
        self.assertEqual(ctx.exception.reason, "AI_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
