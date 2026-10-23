
from app.services.code_parser import extract_code_units
from app.services.repository_loader import discover_source_files


def test_python_parser_extracts_function_and_class():
    source = """
class Calculator:
    def add(self, a, b):
        return a + b


def multiply(a, b):
    return a * b
"""

    result = extract_code_units(source, ".py")
    node_types = {
        unit["node_type"] for unit in result["units"]
    }

    assert "class_definition" in node_types
    assert "function_definition" in node_types


def test_discovery_finds_python_file(tmp_path):
    (tmp_path / "main.py").write_text(
        "def hello():\n    return 'hello'\n",
        encoding="utf-8",
    )

    (tmp_path / "notes.txt").write_text(
        "Ignore this file",
        encoding="utf-8",
    )

    files = discover_source_files(str(tmp_path))

    assert files == [__import__("pathlib").Path("main.py")]


def test_arrow_function_is_not_extracted_twice():
    source = """
const calculateTotal = (price, tax) => {
    return price + tax;
};
"""
    result = extract_code_units(source, ".js")
    units = result["units"]

    # The variable declaration is the code unit we currently extract.
    assert len(units) == 1
    assert units[0]["node_type"] == "lexical_declaration"
    assert "calculateTotal" in units[0]["code"]


def test_function_declaration_is_extracted_once():
    source = """
function calculateTotal(price, tax) {
    return price + tax;
}
"""
    result = extract_code_units(source, ".js")
    units = result["units"]

    assert len(units) == 1
    assert units[0]["node_type"] == "function_declaration"
    assert "calculateTotal" in units[0]["code"]
