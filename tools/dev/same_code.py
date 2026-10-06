"""Comments only? Each changed .lua / .reds / .cpp file's code, comments and spacing taken out, against the last commit's.
  python tools/dev/same_code.py        (exit 1 and the first differing line of each file whose code changed)"""
import os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MARK = {'.lua': '--', '.reds': '//', '.cpp': '//'}


def code(src, mark):
    out = []
    for line in src.splitlines():
        q, i, keep = None, 0, line
        while i < len(line):
            c = line[i]
            if q:
                if c == '\\': i += 1
                elif c == q: q = None
            elif c in '"\'': q = c
            elif line.startswith(mark, i): keep = line[:i]; break
            i += 1
        keep = re.sub(r'\s+', '', keep) if not re.search(r'["\']', keep) else re.sub(r'\s+', ' ', keep).strip()
        if keep: out.append(keep)
    return out


def main():
    os.chdir(ROOT)
    changed = [f for f in subprocess.check_output(['git', 'diff', '--name-only', '--diff-filter=M', 'HEAD'], text=True).split('\n') if os.path.splitext(f)[1] in MARK]
    bad = 0
    for f in changed:
        mark = MARK[os.path.splitext(f)[1]]
        old = code(subprocess.check_output(['git', 'show', 'HEAD:' + f]).decode('utf-8'), mark)
        new = code(open(f, encoding='utf-8').read(), mark)
        if ''.join(old) != ''.join(new):                     # (joined: a statement may move between lines)
            bad += 1
            d = next((i for i, (a, b) in enumerate(zip(old, new)) if a != b), min(len(old), len(new)))
            print('CODE CHANGED %s\n  was: %s\n  now: %s' % (f, old[d][:150] if d < len(old) else '<end>', new[d][:150] if d < len(new) else '<end>'))
    print('%d files changed, %d with code changes' % (len(changed), bad))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
