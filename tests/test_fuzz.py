"""Fuzz testing for PairwiseModel parser and verification."""
import pytest
from hypothesis import given, settings, strategies as st
from pairwise_cli.model import PairwiseModel
from pairwise_cli.verify import verify_pairwise_coverage

# Generate random string names that don't include commas or colons or newlines
valid_string_strategy = st.text(
    alphabet=st.characters(blacklist_categories=('Cc', 'Cs'), blacklist_characters=[',', ':']),
    min_size=1, max_size=20
).map(str.strip).filter(lambda s: len(s) > 0 and not s.startswith('#') and not s.startswith('//'))

@given(
    st.lists(
        st.tuples(
            valid_string_strategy, 
            st.lists(valid_string_strategy, min_size=2, max_size=5, unique_by=lambda x: x.lower())
        ),
        min_size=2, max_size=10, unique_by=lambda t: t[0].lower()
    )
)
@settings(max_examples=100)
def test_fuzz_parser_valid_models(param_data):
    """
    Fuzzes valid model strings through from_pict_model and ensures
    it never crashes for valid syntax limits.
    """
    lines = []
    for name, vals in param_data:
        vals_str = ", ".join(vals)
        lines.append(f"{name}: {vals_str}")
        
    model_str = "\n".join(lines)
    
    # Should safely parse
    model = PairwiseModel.from_pict_model(model_str)
    assert len(model.parameters) == len(param_data)
    
    # Limits validation shouldn't block these small fuzz domains (max 10 params/5 vals)
    model.validate_limits()

@given(st.text(max_size=200))
@settings(max_examples=200)
def test_fuzz_parser_invalid_models(random_text):
    """
    Fuzzes absolutely random unconstrained text and ensures the parser gracefully
    raises ValueError on invalid structures rather than crashing with unhandled exceptions
    like IndexError, KeyError, TypeError, etc.
    """
    try:
        model = PairwiseModel.from_pict_model(random_text)
    except ValueError:
        # Expected behavior for malformed lines/models
        # Will be caught if missing colons, missing names, etc.
        pass
    except Exception as e:
        pytest.fail(f"Parser crashed with unhandled exception: {e}")

def test_hard_limits_raise_validation_errors():
    model = PairwiseModel()
    # Test param limit
    for i in range(51):
        model.add_parameter(f"p{i}", ["v1", "v2"])
        
    with pytest.raises(ValueError, match="exceeding limit of 50"):
        model.validate_limits(max_params=50)
