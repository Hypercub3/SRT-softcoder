import unittest

from srt_softcoder import SrtSoftcoderApp


class BooleanSetting:
    def __init__(self, value: bool) -> None:
        self.value = value

    def get(self) -> bool:
        return self.value


class SrtSoftcoderAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = SrtSoftcoderApp.__new__(SrtSoftcoderApp)
        self.app.output_as_mp4 = BooleanSetting(False)

    def test_supported_video_container_is_kept_by_default(self) -> None:
        self.assertEqual(self.app._default_output_suffix_for_video(".mkv"), ".mkv")

    def test_unsupported_video_container_falls_back_to_mp4(self) -> None:
        self.assertEqual(self.app._default_output_suffix_for_video(".avi"), ".mp4")

    def test_mp4_option_overrides_source_container(self) -> None:
        self.app.output_as_mp4 = BooleanSetting(True)
        self.assertEqual(self.app._default_output_suffix(".mkv"), ".mp4")

    def test_mkv_preserves_supported_subtitle_codec(self) -> None:
        self.assertEqual(self.app._subtitle_codec(".mkv", ".ass"), "ass")

    def test_mp4_uses_mov_text_subtitles(self) -> None:
        self.assertEqual(self.app._subtitle_codec(".mp4", ".srt"), "mov_text")


if __name__ == "__main__":
    unittest.main()
