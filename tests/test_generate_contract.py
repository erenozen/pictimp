"""Generator-level contract tests."""
import pytest
from unittest.mock import patch

from pairwise_cli.generate import generate_suite, GenerationVerificationError
from pairwise_cli.model import PairwiseModel


def build_dummy_model():
    model = PairwiseModel()
    model.add_parameter("A", ["a1", "a2"])
    model.add_parameter("B", ["b1", "b2"])
    return model


def test_require_verified_reports_best_failing_attempt():
    model = build_dummy_model()

    def mock_run_pict(*args, **kwargs):
        return f"seed_{kwargs['seed']}"

    def mock_parse_tsv(content, display_map, canonical_headers):
        seed = int(content.split("_")[-1])
        return canonical_headers, [[str(seed)]]

    def mock_verify(_model, rows):
        seed = int(rows[0][0])
        if seed == 0:
            return False, ["m0_a", "m0_b", "m0_c"]
        if seed == 1:
            return False, ["m1_a"]
        return False, ["m2_a"]

    with patch("pairwise_cli.generate.run_pict", side_effect=mock_run_pict):
        with patch("pairwise_cli.generate.PictOutputParser.parse_tsv", side_effect=mock_parse_tsv):
            with patch("pairwise_cli.generate.verify_pairwise_coverage", side_effect=mock_verify):
                with pytest.raises(GenerationVerificationError) as exc:
                    generate_suite(model, tries=3, verify=True, require_verified=True)

    assert exc.value.missing_pairs == ["m1_a"]


def test_verify_false_keeps_result_unverified_and_lb_none_for_non_two_strength():
    model = build_dummy_model()

    def mock_run_pict(*args, **kwargs):
        return "mock"

    def mock_parse_tsv(_content, _display_map, canonical_headers):
        return canonical_headers, [["a1", "b1"], ["a2", "b2"]]

    with patch("pairwise_cli.generate.run_pict", side_effect=mock_run_pict):
        with patch("pairwise_cli.generate.PictOutputParser.parse_tsv", side_effect=mock_parse_tsv):
            with patch("pairwise_cli.generate.verify_pairwise_coverage") as mock_verify:
                res = generate_suite(
                    model,
                    tries=1,
                    strength=3,
                    verify=False,
                    require_verified=True,
                )

    mock_verify.assert_not_called()
    assert res.passed_verification is False
    assert res.lb is None
