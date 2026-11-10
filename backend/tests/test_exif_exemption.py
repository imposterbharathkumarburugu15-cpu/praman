import unittest
from unittest import mock
from PIL import Image
from ai_engine.forensics import ImageForensicsAnalyzer

class TestExifExemption(unittest.TestCase):
    def test_exif_prevents_ai_flag(self):
        # Set a low disparity threshold to guarantee AI suspicion without EXIF
        analyzer = ImageForensicsAnalyzer(noise_disparity_threshold=1.0)
        img = Image.new('RGB', (64, 64), color='red')
        # Mock getexif to return a non-empty dict (simulating a real camera image)
        with mock.patch.object(img, 'getexif', return_value={271: 'Canon'}):
            result = analyzer.evaluate_tamper(img)
        self.assertFalse(result['is_ai_generated_suspected'], "EXIF image should not be flagged as AI-generated")

if __name__ == '__main__':
    unittest.main()

