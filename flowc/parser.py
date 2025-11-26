from lark import Lark
from .transformer import FlowTransformer


GRAMMAR_FILE = 'grammar.lark'


def get_parser():
    g = open(GRAMMAR_FILE).read()
    return Lark(g, start='start', parser='lalr', propagate_positions=True)


def parse(text):
    parser = get_parser()
    tree = parser.parse(text)
    transformer = FlowTransformer()
    ast = transformer.transform(tree)
    return ast