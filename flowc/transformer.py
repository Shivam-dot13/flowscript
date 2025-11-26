# flowc/transformer.py
from lark import Transformer, Token
from .ast import Workflow, Step, Notify

class FlowTransformer(Transformer):
    # Token conversions
    def NAME(self, tok: Token):
        return str(tok)

    def STRING(self, tok: Token):
        s = str(tok)
        if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
            return s[1:-1]
        return s

    def NUMBER(self, tok: Token):
        return int(str(tok))

    def DURATION(self, tok: Token):
        return str(tok)

    # Small helpers for step fields
    def run(self, items):
        return ('run', items[0])

    def timeout(self, items):
        return ('timeout', items[0])

    def retries(self, items):
        return ('retries', items[0])

    def depends_on(self, items):
        return ('depends_on', items[0])

    def when(self, items):
        return ('when', items[0])

    def on_error(self, items):
        return ('on_error', items[0])

    def trigger(self, items):
        # items: [NAME, STRING]
        return ('trigger', items[0], items[1])

    def env_body(self, items):
        # pass through; may be a flat list or nested lists
        return items

    def env(self, items):
        # items: NAME, env_body (which might be a list-of-items or nested list)
        name = items[0]
        rest = items[1:]
        # Flatten nested lists (safely)
        flat = []
        for it in rest:
            if isinstance(it, list) or isinstance(it, tuple):
                for v in it:
                    flat.append(v)
            else:
                flat.append(it)

        # Now flat should be [KEY, VALUE, KEY2, VALUE2, ...]
        d = {}
        i = 0
        while i < len(flat):
            key = flat[i]
            val = flat[i+1] if i+1 < len(flat) else None
            d[key] = val
            i += 2
        return ('env', name, d)

    def step(self, items):
        name = items[0]
        body = items[1:]
        s = Step(name=name)
        for b in body:
            if isinstance(b, tuple):
                tag = b[0]
                if tag == 'run':
                    s.run = b[1]
                elif tag == 'timeout':
                    s.timeout = b[1]
                elif tag == 'retries':
                    s.retries = int(b[1])
                elif tag == 'depends_on':
                    s.depends_on.append(b[1])
                elif tag == 'on_error':
                    s.on_error = b[1]
                elif tag == 'when':
                    pass
        return s

    def notify_body(self, items):
        return items

    def notify(self, items):
        name = items[0]
        body = items[1] if len(items) > 1 else []
        n = Notify(name=name)
        if len(body) >= 1:
            n.email = body[0]
        if len(body) >= 2:
            n.subject = body[1]
        if len(body) >= 3:
            n.body = body[2]
        return n

    def workflow(self, items):
        name = items[0]
        body = items[1:]
        triggers = []
        env = {}
        steps = []
        notifies = []
        for item in body:
            if isinstance(item, tuple) and item[0] == 'trigger':
                triggers.append((item[1], item[2]))
            elif isinstance(item, tuple) and item[0] == 'env':
                env.update(item[2])
            elif isinstance(item, Step):
                steps.append(item)
            elif isinstance(item, Notify):
                notifies.append(item)
        return Workflow(name=name, triggers=triggers, env=env, steps=steps, notifies=notifies)
