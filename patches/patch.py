import os
import os.path
PATCH_PATH = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_PATH = os.path.join(os.path.dirname(PATCH_PATH), 'WORKSPACE')


def parse(lines: list[str]) -> tuple[bool, list[str]]:
    begs = []
    ends = []
    fles = []
    mode = 0
    for i, l in enumerate(lines):
        if mode % 2 == 0:
            t = l.split('#region patch', 1)
            if len(t) < 2 or t[0].strip() != '--':
                continue
            f = t[1].strip()
            begs.append(i)
            fles.append(f)
        else:
            t = l.split('#endregion patch', 1)
            if len(t) < 2 or t[0].strip() != '--':
                continue
            f = t[1].strip()

            # Optionally confirm that file name matches between start and end markers.
            if f and fles[-1] != f:
                begs.pop()
                fles.pop()
                continue

            ends.append(i)
        mode = mode + 1 % 2

    if len(ends) == 0:
        return False, lines

    res = lines.copy()
    zipped = list(zip(begs, ends, fles))
    for b, e, f in reversed(zipped):
        p = os.path.join(PATCH_PATH, f)
        with open(p, 'r', encoding='utf-8') as o:
            _, res[b + 1:e] = parse(o.readlines())
    return True, res


def patch(name: str) -> None:
    path = os.path.join(WORKSPACE_PATH, name)
    with open(path, 'r', encoding='utf-8') as f:
        old_l = f.readlines()

    changed, new_l = parse(old_l)
    if changed:
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(new_l)


if __name__ == '__main__':
    paths = [
        os.path.join(r, f)
        for r, _, fs in os.walk(WORKSPACE_PATH)
        for f in fs
        if os.path.splitext(f)[1].lower() == '.lua'
    ]
    for p in paths:
        patch(p)
