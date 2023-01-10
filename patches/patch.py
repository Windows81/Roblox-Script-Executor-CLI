import os
import os.path
PATCH_PATH = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_PATH = os.path.join(os.path.dirname(PATCH_PATH), 'WORKSPACE')


def patch_lines(lines: list[str]) -> list[str]:
    begs = []
    ends = []
    fles = []
    mode = 0
    for i, l in enumerate(lines):
        if mode == 0:
            t = l.split('#region patch', 1)
            if len(t) < 2 or t[0].strip() != '--':
                continue
            f = t[1].strip()
            begs.append(i)
            fles.append(f)
            mode = 1
            continue

        t = l.split('#endregion patch', 1)
        if len(t) < 2 or t[0].strip() != '--':
            continue
        f = t[1].strip()

        # Optionally confirm that file name matches between start and end markers.
        if f and fles[-1] != f:
            begs.pop()
            fles.pop()
            continue

        if mode == 0:
            ends[-1] = i
            mode = 1
        else:
            ends.append(i)
            mode = 0

    if len(ends) == 0:
        return lines

    res = lines.copy()
    zipped = list(zip(begs, ends, fles))
    for b, e, f in reversed(zipped):
        path = os.path.join(PATCH_PATH, f)
        res[b + 1:e] = ['\r', *patch_file(path), '\r']
    return res


def patch_file(path: str) -> list[str]:
    with open(path, 'r', encoding='utf-8') as o:
        old_l = o.readlines()

    new_l = patch_lines(old_l)
    if new_l != old_l:
        with open(path, 'w', encoding='utf-8') as o:
            o.writelines(new_l)
    return new_l


if __name__ == '__main__':
    paths = [
        os.path.join(r, f)
        for r, _, fs in os.walk(WORKSPACE_PATH)
        for f in fs
        if os.path.splitext(f)[1].lower() == '.lua'
    ]
    for n in paths:
        patch_file(os.path.join(WORKSPACE_PATH, n))
