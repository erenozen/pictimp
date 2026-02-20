"""Tests for pairwise model, validation, and safe_name mapping."""
from pairwise_cli.model import PairwiseModel, Parameter
from pairwise_cli.util import make_safe_name

def test_make_safe_name():
    existing = set()
    s1 = make_safe_name("Display Mode", existing)
    assert s1 == "Display_Mode"
    existing.add(s1)
    
    s2 = make_safe_name("Display Mode", existing)
    assert s2 == "Display_Mode_2"
    existing.add(s2)
    
    s3 = make_safe_name("!@#", existing)
    assert s3 == "P"
    existing.add(s3)
    
    s4 = make_safe_name("!@#", existing)
    assert s4 == "P_2"

def test_model_serialization():
    model = PairwiseModel()
    model.add_parameter("Language", ["English", "French"])
    model.add_parameter("Display Mode", ["Full", "Text"])
    
    pict_str = model.to_pict_model()
    assert "Language: English, French" in pict_str
    assert "Display_Mode: Full, Text" in pict_str
    
def test_model_parsing():
    content = "Language: English, French\nDisplay_Mode: Full, Text"
    model = PairwiseModel.from_pict_model(content)
    
    assert len(model.parameters) == 2
    assert model.parameters[0].display_name == "Language"
    assert model.parameters[0].safe_name == "Language"
    assert model.parameters[0].values == ["English", "French"]
    
    assert model.parameters[1].display_name == "Display_Mode"
    assert model.parameters[1].safe_name == "Display_Mode"
    assert model.parameters[1].values == ["Full", "Text"]
    
def test_get_counts():
    model = PairwiseModel()
    model.add_parameter("1", ["A", "B"])
    model.add_parameter("2", ["X", "Y", "Z"])
    assert model.get_counts() == [2, 3]

def test_model_reordering():
    model = PairwiseModel()
    model.add_parameter("A", ["1", "2", "3"])
    model.add_parameter("B", ["1", "2", "3", "4"])
    model.add_parameter("C", ["1", "2", "3"])
    model.add_parameter("D", ["1", "2", "3", "4"])
    model.add_parameter("E", ["1", "2", "3"])
    
    # original order: A(3), B(4), C(3), D(4), E(3)
    reordered = model.get_reordered_parameters()
    
    # expected order: B(4), D(4), A(3), C(3), E(3)
    # stable tie-breaks mean B comes before D, and A before C before E
    assert [p.display_name for p in reordered] == ["B", "D", "A", "C", "E"]
