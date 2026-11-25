from copy import deepcopy
from types import SimpleNamespace
import unittest
from ffw.extraction_quality import assess_extraction_quality


class ExtractionQualityTests(unittest.TestCase):
    def test_final_handoff_omission_is_detected_despite_four_plausible_picks(self):
        episode = SimpleNamespace(extraction_profile="cards_to_watch")
        transcript = {"segments": [{"start": 1363, "end": 1370, "text": "My final card to watch is Example Card."}]}
        result = {"section": {"located": True, "start_seconds": 500, "end_seconds": 1700},
                  "recommendations": [{"start_seconds": t, "hosts": []} for t in (500, 680, 900, 900)]}
        assess_extraction_quality(episode, transcript, result)
        self.assertEqual([1363], result["coverage_check"]["unrepresented_seconds"])
        result["recommendations"].append({"start_seconds": 1390, "hosts": []})
        result.pop("coverage_check"); result["review_reason"] = None
        assess_extraction_quality(episode, transcript, result)
        self.assertNotIn("coverage_check", result)

    def test_introduction_and_numbered_speakers_do_not_establish_pick_hosts(self):
        episode = SimpleNamespace(extraction_profile="brainstorm_brewery")
        transcript = {"segments": [
            {"start": 10, "text": "I am Host Alpha, with Host Beta.", "speaker": "Host Alpha"},
            {"start": 100, "text": "My pick is Example.", "speaker": "speaker 1"}]}
        original = deepcopy(transcript)
        result = {"recommendations": [{"start_seconds": 100, "hosts": ["Host Alpha", "Host Beta"]}]}
        assess_extraction_quality(episode, transcript, result)
        self.assertEqual([], result["recommendations"][0]["hosts"])
        self.assertEqual(original, transcript)

    def test_named_label_and_exact_handoff_preserve_supported_attribution(self):
        episode = SimpleNamespace(extraction_profile="brainstorm_brewery")
        for segments in ([{"start": 100, "speaker": "Host Alpha", "text": "My pick is Example."}],
                         [{"start": 90, "text": "Host Alpha, what is your pick?"}]):
            result = {"recommendations": [{"start_seconds": 100, "hosts": ["Host Alpha"]}]}
            assess_extraction_quality(episode, {"segments": segments}, result)
            self.assertEqual(["Host Alpha"], result["recommendations"][0]["hosts"])
