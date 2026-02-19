# -*- coding: utf-8 -*-
"""Развернуть диапазоны в списке ID, убрать уже исправленные по пересчёту заголовков."""

from pathlib import Path

# Список от пользователя (диапазоны через дефис)
USER_IDS_RAW = [
    47, 58, 151, 192, 199, 207, "222-225", 234, 236, 258, 260, 263, 274, 275,
    292, 296, 297, 298, 301, 311, 323, 325, 326, 327, 330, 336, 341, 350, 351,
    "369-371", 382, 391, 398, 411, 426, 429, 433, 436, 441, 460, "478-480",
    503, 511, 512, 529, 547, 549, 554, 556, 557, 560, 594, 608, 609, 737, 764,
    816, "971-1002", 1010, "1057-1061", 1079,
]


def expand_ids(ids_raw):
    out = []
    for x in ids_raw:
        if isinstance(x, int):
            out.append(x)
        elif isinstance(x, str) and "-" in x:
            a, b = x.split("-", 1)
            out.extend(range(int(a.strip()), int(b.strip()) + 1))
        else:
            out.append(int(x))
    return sorted(set(out))


def main():
    project_root = Path(__file__).resolve().parent.parent
    fixed_path = project_root / "logs" / "titles_recalc_affected_ids.txt"
    fixed_ids = set()
    if fixed_path.exists():
        text = fixed_path.read_text(encoding="utf-8").strip()
        fixed_ids = set(int(x) for x in text.split(",") if x.strip())

    user_ids = expand_ids(USER_IDS_RAW)
    already_fixed = sorted(set(user_ids) & fixed_ids)
    pending = sorted(set(user_ids) - fixed_ids)

    print("Полный список ID (диапазоны развёрнуты):", len(user_ids))
    print("Уже исправлены при пересчёте (убираем):", len(already_fixed))
    print("Остались для точечной правки:", len(pending))
    print()
    print("Уже исправлены:", already_fixed)
    print()
    print("Для точечной правки:", pending)

    out_dir = project_root / "logs"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / "titles_pending_ids.txt"
    out_file.write_text(",".join(map(str, pending)), encoding="utf-8")
    print()
    print("Сохранено:", out_file)


if __name__ == "__main__":
    main()
