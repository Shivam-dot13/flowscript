# tests/test_semantic.py
from flowc import parser
from flowc import semantic

EXAMPLE = open("examples/backup.flow").read()

def test_semantic_ok():
    ast = parser.parse(EXAMPLE)
    order = semantic.semantic_check(ast)
    assert "dump_db" in order

def test_cycle_detection():
    bad = 'workflow w { step a { depends_on b run "echo a" } step b { depends_on a run "echo b" } }'
    ast = parser.parse(bad)
    try:
        semantic.semantic_check(ast)
        assert False, "Cycle not detected"
    except Exception:
        assert True
