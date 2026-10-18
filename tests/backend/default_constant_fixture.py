"""Evaluate only shipped constant assignments with an empty environment."""
import ast
from pathlib import Path
from types import SimpleNamespace

def shipped_constants(module,names):
    scope={'Path':Path,'os':SimpleNamespace(environ={})};wanted=set(names)
    for node in ast.parse(Path(module.__file__).read_text()).body:
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in wanted:
            scope[node.targets[0].id]=eval(compile(ast.Expression(node.value),'<shipped default>','eval'),scope)
    assert wanted<=scope.keys()
    return {name:scope[name] for name in names}
