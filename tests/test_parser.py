from flowc import parser


EXAMPLE = open('examples/backup.flow').read()


def test_parse_example():
    ast = parser.parse(EXAMPLE)
    assert ast.name == 'backup_and_notify'
    assert len(ast.steps) >= 2