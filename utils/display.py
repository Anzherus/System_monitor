from typing import Iterable, Sequence


def header(title, width: int = 60):
    print(title.center(width))


def table(rows, headers: Sequence[str] = None):
    if not rows:
        print("(нет данных)")
        return
    cols = len(rows[0])
    widths = [max(len(str(r[i])) for r in rows) for i in range(cols)]
    if headers:
        widths = [max(w, len(h)) for w, h in zip(widths, headers)]
        print(" | ".join(str(h).ljust(w) for h, w in zip(headers, widths)))
        print("-+-".join("-" * w for w in widths))
    for row in rows:
        print(" | ".join(str(c).ljust(w) for c, w in zip(row, widths)))