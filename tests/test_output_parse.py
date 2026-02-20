from pairwise_cli.output import PictOutputParser

def test_parse_tsv():
    content = "Lang\tDisplay_Mode\nEnglish\tFull\nFrench\tText"
    mapping = {"Lang": "Language", "Display_Mode": "Display Mode"}
    
    headers, rows = PictOutputParser.parse_tsv(content, mapping)
    
    assert headers == ["Language", "Display Mode"]
    assert len(rows) == 2
    assert rows[0] == ["English", "Full"]
    assert rows[1] == ["French", "Text"]
    
def test_parse_tsv_with_canonical_headers():
    content = "Lang\tDisplay_Mode\nEnglish\tFull\nFrench\tText"
    mapping = {"Lang": "Language", "Display_Mode": "Display Mode"}
    canonical = ["Display Mode", "Language"]
    
    headers, rows = PictOutputParser.parse_tsv(content, mapping, canonical_headers=canonical)
    
    assert headers == ["Display Mode", "Language"]
    assert len(rows) == 2
    assert rows[0] == ["Full", "English"]
    assert rows[1] == ["Text", "French"]

def test_parse_empty():
    headers, rows = PictOutputParser.parse_tsv("   \n \n", {})
    assert headers == []
    assert rows == []
