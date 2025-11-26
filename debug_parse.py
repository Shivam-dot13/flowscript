from lark import Lark, Tree
grammar = open("grammar.lark").read()

parser = Lark(grammar, start="start", parser="lalr", propagate_positions=True)

src = open("examples/backup.flow").read()
tree = parser.parse(src)

print(tree.pretty())
