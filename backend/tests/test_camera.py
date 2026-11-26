"""Preview frames are reduced for the dashboard; OCR frames stay full size and fresh."""
import io
import unittest
from unittest.mock import MagicMock

try:
    from PIL import Image
except ImportError:  # Pillow comes with picamera2 on the Pi; skip where it is missing
    Image = None

from backend.app.camera import Camera


@unittest.skipIf(Image is None, "Pillow not installed")
class CameraTests(unittest.TestCase):
    def camera(self):
        camera = Camera(width=1920, height=1080)
        camera.enabled = True
        fake = MagicMock()
        fake.capture_image.side_effect = lambda stream: Image.new("RGB", (1920, 1080), "white")
        camera._camera = fake  # skip Picamera2 start
        return camera, fake

    @staticmethod
    def size(jpeg):
        return Image.open(io.BytesIO(jpeg)).size

    def test_preview_is_reduced_and_shared_between_close_requests(self):
        camera, fake = self.camera()
        first = camera.preview_jpeg()
        self.assertEqual(self.size(first), (640, 360))
        self.assertIs(camera.preview_jpeg(), first)  # within min_interval_s
        self.assertEqual(fake.capture_image.call_count, 1)

    def test_full_frame_is_full_size_and_never_cached(self):
        camera, fake = self.camera()
        self.assertEqual(self.size(camera.full_jpeg()), (1920, 1080))
        camera.full_jpeg()
        self.assertEqual(fake.capture_image.call_count, 2)


if __name__ == "__main__":
    unittest.main()
