"""One structure renderer for previews, stored events and portable documents."""
from pathlib import PurePosixPath


def render_structure(year, folder, day_keys=(), children=(), preserve_days=False):
    paths = []
    branches = [''] + [str(c.get('folder_name') or c.get('folder') or '') for c in children]
    for branch in dict.fromkeys(branches):
        for day in (sorted(set(day_keys)) if preserve_days and day_keys else ['']):
            for leaf in ('Alle','Sortiert','Export'):
                paths.append('/'.join(x for x in [str(year),str(folder),branch,day,leaf] if x))
    tree = {}
    for path in paths:
        cursor = tree
        for part in PurePosixPath(path).parts:
            cursor = cursor.setdefault(part,{})
    lines=[]
    def walk(node, prefix='', root=False):
        for i,(name,children) in enumerate(node.items()):
            last=i==len(node)-1
            lines.append(prefix+('' if root else ('└── ' if last else '├── '))+name)
            walk(children,prefix+('' if root else ('    ' if last else '│   ')))
    walk(tree,root=True)
    return lines
