"""
GUI для телескопического разложения кубов + параметрическая форма (квадратики по x; см. публ. 06).
Файл clear_result.py должен лежать в той же папке (в архиве decompose_gui_EXT_windows.zip или с публ. 5).

Запуск:
  python decompose_gui_EXT.py
"""

import sys
import traceback
from typing import Optional, Tuple
import webbrowser
from pathlib import Path

import sympy as sp

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox

_DIR = Path(__file__).resolve().parent
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

from clear_result import (  # noqa: E402
    compute_ramanujan_decomposition,
    format_factorization,
    order_sides_for_display,
    ru_cubes_phrase,
    try_defactored_equation_lines,
    wrap_equation_lines,
)

AUTHOR_SITE_URL = "https://nvvorobtsov.github.io/"

# Заголовок блока: g — НОД всех оснований кубов до деления; сокращение на g даёт тождество для суммы, делённой на g³.
DEFACTOR_SECTION_TITLE = "После дефакторизации (g³ — куб НОД всех оснований):"

TITLE_FACTORED_CUBES = "С полной факторизацией результата*:"
TITLE_FACTORED_TABLE = "Или с факторизацией оснований результата*:"
FOOTNOTE_DEFACT_REDUCED = "* Имеется в виду сокращённое тождество после дефакторизации."

TAG_PRIME_TABLE_ROW = "prime_table_row"
TABLE_PRIME_BLUE = "#1565C0"


def _highlight_prime_or_unit_base(x) -> bool:
    """Подсветка строки таблицы: простое основание или 1 (у 1 нет нетривиальной факторизации)."""
    v = abs(int(x))
    if v == 1:
        return True
    return v >= 2 and bool(sp.isprime(v))


def _actual_text_widget(st: tk.Widget) -> tk.Text:
    """У ScrolledText реальный Text может быть self или дочерний — от версии Python."""
    inner = getattr(st, "text", None)
    if isinstance(inner, tk.Text):
        return inner
    if isinstance(st, tk.Text):
        return st
    for ch in st.winfo_children():
        if isinstance(ch, tk.Text):
            return ch
    return st  # на случай нестандартной обёртки


def _estimate_wrap_chars(text_w: tk.Widget) -> int:
    """Сколько символов моноширинного шрифта помещается по ширине виджета (для рубки строк)."""
    tw = _actual_text_widget(text_w)
    tw.update_idletasks()
    px = tw.winfo_width()
    if px < 80:
        px = max(tw.winfo_reqwidth(), 720)
    try:
        fn = tkfont.Font(font=tw.cget("font"))
        cw = fn.measure("8")
        if cw <= 0:
            cw = 7
    except tk.TclError:
        cw = 7
    inner = max(px - 28, 64)
    n = max(inner // cw, 48)
    return min(int(n), 5000)


# (a, b₀, k, число членов) — при b₀=0 и этих a,k слева от «=» ровно один куб, справа — остальное, без «-»
PRESET_EXAMPLES = [
    (50, 0, 4, 10),
    (50, 0, 49, 100),
    (50, 0, 499, 1000),
    (50, 0, 4999, 10000),
    (50, 0, 24999, 50000),
    (50, 0, 49999, 100000),
    (100, 0, 249999, 500000),
]

PRESET_TARGETS_RU = [
    "~10 членов, слева: 1 куб",
    "~100, слева: 1 куб",
    "~1000, слева: 1 куб",
    "~10000, слева: 1 куб",
    "~50000, слева: 1 куб",
    "~100000, слева: 1 куб",
    "~500000, слева: 1 куб (a=100)",
]


def build_output_parts(data: dict, *, wrap_width: int = 72):
    """Полный вывод: шапка, строки тождества (wrap), нижняя линия из =."""
    bar_w = min(max(wrap_width, 40), 200)
    sep = "=" * bar_w
    Ld, Rd = order_sides_for_display(data["L_final"], data["R_final"])
    header = [
        (
            f"Разложение: a = {data['a']}, b₀ = {data['b_start']}, k = {data['k']}"
        ),
        f"Параметры сформированы. Число членов в последовательности: {data['total_terms']}.",
        "",
        "Результат:",
        f"Слева: {ru_cubes_phrase(len(Ld))}",
        f"Справа: {ru_cubes_phrase(len(Rd))}",
        sep,
        f"{data['total_val']} = {data['factor_str']} =",
    ]
    eq_lines = wrap_equation_lines(Ld, Rd, wrap_width)
    return header, eq_lines, sep


def wrap_factored_cube_equation(L: list, R: list, width: int) -> list:
    """Строки тождества (как wrap_equation_lines), но основания — полная факторизация в скобках."""
    tokens = []
    for i, val in enumerate(L):
        fx = format_factorization(val)
        tok = f"({fx})^3"
        tokens.append(tok if i == 0 else f"+{tok}")
    tokens.append("=")
    for i, val in enumerate(R):
        fx = format_factorization(val)
        tok = f"({fx})^3"
        tokens.append(tok if i == 0 else f"+{tok}")
    lines = []
    current_line = ""
    for token in tokens:
        if token == "=":
            current_line += " = "
            continue
        if len(current_line) + len(token) > width:
            if current_line.strip():
                lines.append(current_line.rstrip())
            current_line = token
        else:
            current_line += token
    if current_line.strip():
        lines.append(current_line.rstrip())
    return lines


def format_bases_factor_table(L: list, R: list) -> tuple[list[str], list[Optional[str]]]:
    """Таблица: целое основание | разложение format_factorization (моноширинно).

    Второй список — теги по строкам (None или TAG_PRIME_TABLE_ROW для строк данных с простым основанием).
    """
    bases_order = [int(x) for x in L] + [int(x) for x in R]
    rows = []
    for x in L:
        rows.append((str(int(x)), format_factorization(x)))
    for x in R:
        rows.append((str(int(x)), format_factorization(x)))
    h0, h1 = "Основание", "Факторизация"
    wn = max(len(h0), max((len(r[0]) for r in rows), default=0))
    wf = max(len(h1), max((len(r[1]) for r in rows), default=0))
    sep = "+" + "-" * (wn + 2) + "+" + "-" * (wf + 2) + "+"
    out = [
        sep,
        "| " + h0.rjust(wn) + " | " + h1.ljust(wf) + " |",
        sep,
    ]
    tags: list[Optional[str]] = [None, None, None]
    for i, (n, fac) in enumerate(rows):
        out.append("| " + n.rjust(wn) + " | " + fac.ljust(wf) + " |")
        tags.append(TAG_PRIME_TABLE_ROW if _highlight_prime_or_unit_base(bases_order[i]) else None)
    out.append(sep)
    tags.append(None)
    return out, tags


def _factor_string_tokens(fac_str: str) -> list[str]:
    s = (fac_str or "").strip()
    if not s:
        return []
    return s.split("*")


def format_bases_factor_table_by_columns(
    L: list,
    R: list,
    *,
    h_base: str = "Основание",
) -> tuple[list[str], list[Optional[str]]]:
    """Таблица: основание | фактор 1 | фактор 2 | … (моноширинно, ячейки факторов выровнены вправо).

    Второй список — теги по строкам (как у format_bases_factor_table).
    """
    bases_order = [int(x) for x in L] + [int(x) for x in R]
    rows = []
    for x in L:
        rows.append((str(int(x)), format_factorization(x)))
    for x in R:
        rows.append((str(int(x)), format_factorization(x)))
    factor_rows = [_factor_string_tokens(f) for _, f in rows]
    nf = max((len(fr) for fr in factor_rows), default=0)
    if nf < 1:
        nf = 1
    wn = max(len(h_base), max((len(r[0]) for r in rows), default=0))
    col_widths = []
    for j in range(nf):
        h = str(j + 1)
        w = len(h)
        for fr in factor_rows:
            if j < len(fr):
                w = max(w, len(fr[j]))
        col_widths.append(max(w, 1))
    parts = ["+" + "-" * (wn + 2)] + ["+" + "-" * (cw + 2) for cw in col_widths] + ["+"]
    sep = "".join(parts)
    header_line = "| " + h_base.rjust(wn) + " |"
    for j, cw in enumerate(col_widths):
        header_line += " " + str(j + 1).center(cw) + " |"
    out = [sep, header_line, sep]
    tags: list[Optional[str]] = [None, None, None]
    for row_i, ((_n, _f), fr) in enumerate(zip(rows, factor_rows)):
        row_line = "| " + _n.rjust(wn) + " |"
        for j, cw in enumerate(col_widths):
            cell = fr[j] if j < len(fr) else ""
            row_line += " " + cell.rjust(cw) + " |"
        out.append(row_line)
        tags.append(TAG_PRIME_TABLE_ROW if _highlight_prime_or_unit_base(bases_order[row_i]) else None)
    out.append(sep)
    tags.append(None)
    return out, tags


def build_full_factor_display(
    L2: list,
    R2: list,
    wrap_width: int,
    *,
    bases_only: bool,
    factor_columns: bool = False,
):
    """(mode, lines, line_tags): line_tags выравнивается с lines или None для режима cubes."""
    foot = FOOTNOTE_DEFACT_REDUCED
    if bases_only:
        if factor_columns:
            body, body_tags = format_bases_factor_table_by_columns(L2, R2)
        else:
            body, body_tags = format_bases_factor_table(L2, R2)
        lines = [TITLE_FACTORED_TABLE] + body + [foot]
        line_tags = [None] + body_tags + [None]
        return ("table", lines, line_tags)
    body = wrap_factored_cube_equation(L2, R2, wrap_width)
    lines = [TITLE_FACTORED_CUBES] + body + [foot]
    return ("cubes", lines, None)


def between_separators_one_line(
    data: dict,
    wrap_width: int,
    defactor_bundle: Optional[Tuple[str, str, list, list, list]] = None,
    omit_raw_decomposition: bool = False,
    between_tail_lines: Optional[list] = None,
) -> str:
    """Текст между линиями === без переносов (как одна строка) для копирования."""
    tail = ("\n" + "\n".join(between_tail_lines)) if between_tail_lines else ""
    if omit_raw_decomposition and defactor_bundle:
        d_g3, d_n, d_eq, _L2, _R2 = defactor_bundle
        s = (
            DEFACTOR_SECTION_TITLE
            + "\n"
            + d_g3
            + "\n"
            + d_n
            + "\n"
            + "\n".join(d_eq)
        )
        return s + tail
    header, eq_lines, _ = build_output_parts(data, wrap_width=wrap_width)
    factor_line = header[-1]
    s = factor_line.rstrip() + "".join(eq_lines)
    if defactor_bundle:
        d_g3, d_n, d_eq, _L2, _R2 = defactor_bundle
        s += (
            "\n"
            + DEFACTOR_SECTION_TITLE
            + "\n"
            + d_g3
            + "\n"
            + d_n
            + "\n"
            + "\n".join(d_eq)
        )
    return s + tail


def build_output(data: dict, term_count_only: bool, *, wrap_width: int = 72) -> str:
    if term_count_only:
        Ld, Rd = order_sides_for_display(data["L_final"], data["R_final"])
        return (
            f"a = {data['a']}, b₀ = {data['b_start']}, k = {data['k']}\n"
            f"Членов в разложении (после сокращений): {data['total_terms']}\n"
            f"Слева: {ru_cubes_phrase(len(Ld))}\n"
            f"Справа: {ru_cubes_phrase(len(Rd))}\n"
        )
    h, e, s = build_output_parts(data, wrap_width=wrap_width)
    return "\n".join(h + e + [s])


class ParametricAnalysisError(Exception):
    """Не удалось восстановить квадратики по x = 10ⁿ при b₀ = 10ⁿ − 1."""


# Редкие тождества Σ S1 = Σ S2 / Σ S1² = Σ S2² — крупный красный жирный текст в окне результата.
TAG_PARAMETRIC_SHOUT = "parametric_shout"


def parametric_block_has_shout(rows: list[tuple[str, Optional[str]]]) -> bool:
    return any(tag == TAG_PARAMETRIC_SHOUT for _, tag in rows if tag)


def insert_parametric_analysis_lines(
    tw: tk.Text, rows: list[tuple[str, Optional[str]]]
) -> None:
    """Вставка блока параметрической формы; строки с тегом TAG_PARAMETRIC_SHOUT — «крик»."""
    try:
        base = tkfont.Font(font=tw.cget("font"))
        fam = base.actual("family")
        sz = int(base.actual("size"))
        tw.tag_configure(
            TAG_PARAMETRIC_SHOUT,
            font=(fam, min(sz + 8, 26), "bold"),
            foreground="#C62828",
        )
    except tk.TclError:
        tw.tag_configure(
            TAG_PARAMETRIC_SHOUT,
            font=("Consolas", 18, "bold"),
            foreground="#C62828",
        )
    for line, tag in rows:
        if tag:
            tw.insert(tk.END, line + "\n", tag)
        else:
            tw.insert(tk.END, line + "\n")


_SUP_DIGITS = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def _superscript_int(n: int) -> str:
    return str(int(n)).translate(_SUP_DIGITS)


def _rational_abs_display(c: sp.Rational) -> str:
    c = abs(sp.Rational(c))
    if c.q == 1:
        return str(int(c.p))
    return f"{c.p}/{c.q}"


def format_polynomial_line(expr: sp.Expr, x_sym: sp.Symbol, *, x_label: str = "x") -> str:
    """Одна строка: полином над ℚ в переменной x (Unicode степени)."""
    poly = sp.Poly(sp.expand(expr), x_sym, domain="QQ")
    if poly.is_zero:
        return "0"
    pairs = sorted(poly.terms(), key=lambda t: t[0][0], reverse=True)
    out: list[str] = []
    first = True
    for (exp,), coef in pairs:
        c = sp.Rational(coef)
        if c == 0:
            continue
        sign_neg = c < 0
        cabs = abs(c)
        if first:
            if sign_neg:
                out.append("−")
            first = False
        else:
            out.append(" − " if sign_neg else " + ")
        if exp == 0:
            out.append(_rational_abs_display(cabs))
            continue
        if cabs == 1:
            coef_txt = ""
        else:
            coef_txt = _rational_abs_display(cabs) + "·"
        if exp == 1:
            out.append(coef_txt + x_label)
        else:
            out.append(coef_txt + x_label + _superscript_int(exp))
    return "".join(out) if out else "0"


def b0_is_all_nines(b0: int) -> bool:
    if b0 <= 0:
        return False
    s = str(b0)
    return s == "9" * len(s)


# Имена оснований в блоке параметрической формы — a…z (не более 26 кубов на сторону).
PARAMETRIC_MAX_CUBES_PER_SIDE = 26


def parametric_form_eligible_for_last_run(data: dict) -> bool:
    """Условия активации кнопки «Параметрическая форма» по данным последнего полного расчёта."""
    if not b0_is_all_nines(data["b_start"]):
        return False
    Ld, Rd = order_sides_for_display(data["L_final"], data["R_final"])
    nL, nR = len(Ld), len(Rd)
    if nL != nR:
        return False
    return 1 <= nL <= PARAMETRIC_MAX_CUBES_PER_SIDE


# Три масштаба: x = 10⁷, 10⁶, 10⁵ при b₀ = 10ⁿ − 1 (внутренний расчёт; в интерфейсе — проверка на n=6).
_PARAMETRIC_N_DIGITS = (7, 6, 5)


def _sorted_display_sides(
    a: int, k: int, n_digits: int
) -> tuple[list[int], list[int]]:
    b0 = 10**n_digits - 1
    data = compute_ramanujan_decomposition(a, b0, k, factorize=False)
    Ld, Rd = order_sides_for_display(data["L_final"], data["R_final"])
    return sorted(int(x) for x in Ld), sorted(int(x) for x in Rd)


def build_parametric_analysis_block(a: int, k: int) -> list[tuple[str, Optional[str]]]:
    """Строки блока параметрической формы; (текст, TAG_PARAMETRIC_SHOUT) для редких сумм/сумм квадратов."""
    sides: list[tuple[list[int], list[int]]] = []
    for n in _PARAMETRIC_N_DIGITS:
        sides.append(_sorted_display_sides(a, k, n))
    n_hi, n_mid, n_lo = _PARAMETRIC_N_DIGITS
    x_hi, x_mid, x_lo = 10**n_hi, 10**n_mid, 10**n_lo
    L0, R0 = sides[0]
    if len(L0) != len(R0):
        raise ParametricAnalysisError(
            "Число кубов слева и справа не совпадает; параметрическая форма недоступна."
        )
    if len(L0) > PARAMETRIC_MAX_CUBES_PER_SIDE:
        raise ParametricAnalysisError(
            f"Слишком много кубов на стороне (лимит {PARAMETRIC_MAX_CUBES_PER_SIDE})."
        )
    for i in (1, 2):
        Li, Ri = sides[i]
        if len(Li) != len(L0) or len(Ri) != len(R0):
            raise ParametricAnalysisError(
                "Число кубов на сторонах меняется с масштабом b₀ (10ⁿ−1); "
                "сопоставление по индексу невозможно."
            )
    x_sym = sp.Symbol("x")
    L_polys: list[sp.Expr] = []
    R_polys: list[sp.Expr] = []
    for idx in range(len(L0)):
        pts_l = [
            (x_hi, sp.Integer(sides[0][0][idx])),
            (x_mid, sp.Integer(sides[1][0][idx])),
            (x_lo, sp.Integer(sides[2][0][idx])),
        ]
        pl = sp.expand(sp.interpolate(pts_l, x_sym))
        if sp.degree(pl, x_sym) > 2:
            raise ParametricAnalysisError("Слева: восстановленный полином степени > 2.")
        L_polys.append(pl)
    for idx in range(len(R0)):
        pts_r = [
            (x_hi, sp.Integer(sides[0][1][idx])),
            (x_mid, sp.Integer(sides[1][1][idx])),
            (x_lo, sp.Integer(sides[2][1][idx])),
        ]
        pr = sp.expand(sp.interpolate(pts_r, x_sym))
        if sp.degree(pr, x_sym) > 2:
            raise ParametricAnalysisError("Справа: восстановленный полином степени > 2.")
        R_polys.append(pr)
    for idx, p in enumerate(L_polys):
        if int(p.subs(x_sym, x_mid)) != sides[1][0][idx]:
            raise ParametricAnalysisError(
                "Проверка b₀ = 10⁶−1: значения S1 не совпали с вычислением."
            )
    for idx, p in enumerate(R_polys):
        if int(p.subs(x_sym, x_mid)) != sides[1][1][idx]:
            raise ParametricAnalysisError(
                "Проверка b₀ = 10⁶−1: значения S2 не совпали с вычислением."
            )
    sum_L3 = sp.expand(sum(p**3 for p in L_polys))
    sum_R3 = sp.expand(sum(p**3 for p in R_polys))
    if sp.expand(sum_L3 - sum_R3) != 0:
        raise ParametricAnalysisError("Суммы кубов полиномов S1 и S2 не совпадают.")
    P = sum_L3
    sum_L1 = sp.expand(sum(L_polys))
    sum_R1 = sp.expand(sum(R_polys))
    lin_ok = sp.expand(sum_L1 - sum_R1) == 0
    sum_L2 = sp.expand(sum(p**2 for p in L_polys))
    sum_R2 = sp.expand(sum(p**2 for p in R_polys))
    sq_ok = sp.expand(sum_L2 - sum_R2) == 0

    def _name(i: int) -> str:
        return chr(ord("a") + i) if i < 26 else f"t{i + 1}"

    rows: list[tuple[str, Optional[str]]] = [
        ("", None),
        (
            "— Параметрическая форма (внутренний расчёт при b₀ = 10⁷−1, 10⁶−1, 10⁵−1; "
            "проверено совпадение при b₀ = 10⁶−1) —",
            None,
        ),
        (
            f"a = {a},  k = {k}   (x соответствует степени десяти: при b₀ = 10ⁿ−1 подставляйте x = 10ⁿ)",
            None,
        ),
        ("", None),
        ("Группа S1 — основания кубов слева от «=» (квадратики по x)", None),
    ]
    for i, p in enumerate(L_polys):
        rows.append((f"{_name(i)}₁ = {format_polynomial_line(p, x_sym)}", None))
    rows.append(("", None))
    rows.append(
        ("Группа S2 — основания кубов справа от «=» (квадратики по x)", None),
    )
    for i, p in enumerate(R_polys):
        rows.append((f"{_name(i)}₂ = {format_polynomial_line(p, x_sym)}", None))
    rows.append(("", None))
    rows.append(
        ("Инвариантный многочлен P(x) = Σ S1³ = Σ S2³ (обе стороны)", None),
    )
    rows.append((format_polynomial_line(P, x_sym), None))
    rows.append(("", None))
    rows.append(("Дополнительные тождества по суммам (не в кубах):", None))
    if lin_ok:
        rows.append(
            (
                "!!! ВНИМАНИЕ !!!  Σ S1 = Σ S2  ВЫПОЛНЯЕТСЯ  —  НЕОБЫЧНО !!!",
                TAG_PARAMETRIC_SHOUT,
            ),
        )
    else:
        rows.append(("Σ S1 = Σ S2  — не выполняется.", None))
    if sq_ok:
        rows.append(
            (
                "!!! ВНИМАНИЕ !!!  Σ S1² = Σ S2²  ВЫПОЛНЯЕТСЯ  —  НЕОБЫЧНО !!!",
                TAG_PARAMETRIC_SHOUT,
            ),
        )
    else:
        rows.append(("Σ S1² = Σ S2² — не выполняется.", None))
    return rows


def _insert_eq_lines_bold_left(tw: tk.Text, lines: list, tag: str) -> None:
    """Левая часть до первого « = » — жирным (tag)."""
    left_zone = True
    for line in lines:
        if left_zone:
            if " = " in line:
                left_part, _, rest = line.partition(" = ")
                tw.insert(tk.END, left_part, (tag,))
                tw.insert(tk.END, " = " + rest + "\n")
                left_zone = False
            else:
                tw.insert(tk.END, line + "\n", (tag,))
        else:
            tw.insert(tk.END, line + "\n")


def insert_result_with_bold_left_side(
    tw: tk.Text,
    header: list,
    eq_lines: list,
    sep: str,
    defactor_bundle: Optional[Tuple[str, str, list, list, list]] = None,
    full_factor_display: Optional[Tuple[str, list, Optional[list]]] = None,
) -> None:
    """В строках тождества левая часть до первого « = » — жирным и синим (#1565C0)."""
    tag = "decomp_left"
    blue = "#1565C0"
    try:
        base = tkfont.Font(font=tw.cget("font"))
        fam = base.actual("family")
        sz = int(base.actual("size"))
        tw.tag_configure(tag, font=(fam, sz, "bold"), foreground=blue)
    except tk.TclError:
        tw.tag_configure(tag, font=("Consolas", 10, "bold"), foreground=blue)

    for line in header:
        tw.insert(tk.END, line + "\n")

    _insert_eq_lines_bold_left(tw, eq_lines, tag)

    if defactor_bundle:
        d_g3, d_n, d_eq, _L2, _R2 = defactor_bundle
        if eq_lines:
            tw.insert(tk.END, "\n")
        tw.insert(tk.END, DEFACTOR_SECTION_TITLE + "\n")
        tw.insert(tk.END, d_g3 + "\n")
        tw.insert(tk.END, d_n + "\n")
        _insert_eq_lines_bold_left(tw, d_eq, tag)

    if full_factor_display:
        mode, lines, line_tags = full_factor_display
        tw.insert(tk.END, "\n")
        tw.insert(tk.END, lines[0] + "\n")
        mid = lines[1:-1]
        if mode == "cubes":
            _insert_eq_lines_bold_left(tw, mid, tag)
        else:
            if line_tags:
                try:
                    bf = tkfont.Font(font=tw.cget("font"))
                    fam = bf.actual("family")
                    sz = int(bf.actual("size"))
                    tw.tag_configure(
                        TAG_PRIME_TABLE_ROW,
                        font=(fam, sz, "bold"),
                        foreground=TABLE_PRIME_BLUE,
                    )
                except tk.TclError:
                    tw.tag_configure(
                        TAG_PRIME_TABLE_ROW,
                        font=("Consolas", 10, "bold"),
                        foreground=TABLE_PRIME_BLUE,
                    )
            for i, ln in enumerate(mid):
                tidx = 1 + i
                tg = (
                    line_tags[tidx]
                    if line_tags and tidx < len(line_tags) and line_tags[tidx]
                    else None
                )
                if tg:
                    tw.insert(tk.END, ln + "\n", (tg,))
                else:
                    tw.insert(tk.END, ln + "\n")
        tw.insert(tk.END, lines[-1] + "\n")

    tw.insert(tk.END, sep + "\n")


def main():
    root = tk.Tk()
    root.title("Ramanujan decomposition — параметры a, b₀, k")
    root.minsize(640, 880)

    frm = ttk.Frame(root, padding=12)
    frm.grid(row=0, column=0, sticky="nsew")
    root.rowconfigure(0, weight=1)
    root.columnconfigure(0, weight=1)
    frm.columnconfigure(1, weight=1)
    frm.rowconfigure(9, weight=1)

    var_a = tk.IntVar(value=2)
    var_b = tk.IntVar(value=10)
    var_k = tk.IntVar(value=5)
    var_warn_max = tk.IntVar(value=50000)
    var_auto_parametric = tk.BooleanVar(value=False)

    ttk.Label(frm, text="a:").grid(row=0, column=0, sticky="w", pady=2)
    sp_a = tk.Spinbox(
        frm,
        from_=-300,
        to=300,
        increment=1,
        textvariable=var_a,
        width=12,
    )
    sp_a.grid(row=0, column=1, sticky="w", pady=2)

    ttk.Label(frm, text="b₀ (начальное b):").grid(row=1, column=0, sticky="w", pady=2)
    sp_b = tk.Spinbox(
        frm,
        from_=-20000,
        to=20000,
        increment=1,
        textvariable=var_b,
        width=12,
    )
    sp_b.grid(row=1, column=1, sticky="w", pady=2)

    ttk.Label(frm, text="k (число шагов):").grid(row=2, column=0, sticky="w", pady=2)
    sp_k = tk.Spinbox(
        frm,
        from_=1,
        to=300000,
        increment=1,
        textvariable=var_k,
        width=12,
    )
    sp_k.grid(row=2, column=1, sticky="w", pady=2)

    only_count = tk.BooleanVar(value=False)
    chk = ttk.Checkbutton(
        frm,
        text="Только число членов (без строки разложения)",
        variable=only_count,
    )
    chk.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 4))

    var_defactor = tk.BooleanVar(value=True)
    chk_def = ttk.Checkbutton(
        frm,
        text=(
            "Проверка дефакторизации (g³ = (НОД оснований)³, N = факторизация(N) =, сокращённое "
            "тождество; при НОД>1 сырое разложение не показывается; при НОД=1 — полный вывод)"
        ),
        variable=var_defactor,
    )
    chk_def.grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 4))

    var_full_factor = tk.BooleanVar(value=False)
    var_bases_only = tk.BooleanVar(value=True)
    opt_sub = ttk.Frame(frm)
    opt_sub.grid(row=5, column=0, columnspan=2, sticky="w", pady=(0, 4))
    chk_ff = ttk.Checkbutton(
        opt_sub,
        text=(
            "Полная факторизация сокращённого тождества (кубы с разложенными основаниями; "
            "ниже блок после дефакторизации)"
        ),
        variable=var_full_factor,
    )
    chk_ff.pack(side=tk.LEFT)
    chk_bo = ttk.Checkbutton(
        opt_sub,
        text="Только основания (таблица, без ^3)",
        variable=var_bases_only,
    )
    chk_bo.pack(side=tk.LEFT, padx=(18, 0))

    var_factor_columns = tk.BooleanVar(value=False)
    chk_fc = ttk.Checkbutton(
        opt_sub,
        text="Факторы по колонкам таблицы",
        variable=var_factor_columns,
    )
    chk_fc.pack(side=tk.LEFT, padx=(18, 0))

    def sync_factor_suboptions(*_args):
        ff = var_full_factor.get()
        bo = var_bases_only.get()
        st_sub = tk.NORMAL if ff else tk.DISABLED
        chk_bo.configure(state=st_sub)
        chk_fc.configure(state=tk.NORMAL if (ff and bo) else tk.DISABLED)

    var_full_factor.trace_add("write", sync_factor_suboptions)
    var_bases_only.trace_add("write", sync_factor_suboptions)
    sync_factor_suboptions()

    ttk.Label(
        frm,
        text=(
            "Макс. членов разложения — предупреждать о большом выводе\n"
            "(только если галочка «только число» выключена):"
        ),
        justify=tk.LEFT,
    ).grid(row=6, column=0, sticky="nw", pady=2)
    sp_warn = tk.Spinbox(
        frm,
        from_=4,
        to=2_000_000,
        increment=1,
        textvariable=var_warn_max,
        width=12,
    )
    sp_warn.grid(row=6, column=1, sticky="w", pady=2)

    ex_frame = ttk.LabelFrame(frm, text="Примеры: тройка параметров → число членов (для ориентира)")
    ex_frame.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(10, 6))
    ex_frame.columnconfigure(0, weight=1)

    ttk.Label(ex_frame, text="Параметры a, b₀, k").grid(row=0, column=0, sticky="w", padx=4, pady=2)
    ttk.Label(ex_frame, text="Членов").grid(row=0, column=1, sticky="w", padx=4, pady=2)
    ttk.Label(ex_frame, text="").grid(row=0, column=2, padx=2, pady=2)

    def make_apply(a_i, b_i, k_i):
        def _apply():
            var_a.set(a_i)
            var_b.set(b_i)
            var_k.set(k_i)

        return _apply

    for i, ((a_i, b_i, k_i, cnt), hint) in enumerate(
        zip(PRESET_EXAMPLES, PRESET_TARGETS_RU), start=1
    ):
        param_txt = f"a = {a_i},  b₀ = {b_i},  k = {k_i}"
        row_txt = f"{param_txt}   ({hint})"
        ttk.Label(ex_frame, text=row_txt).grid(row=i, column=0, sticky="w", padx=4, pady=1)
        ttk.Label(ex_frame, text=str(cnt)).grid(row=i, column=1, sticky="e", padx=8, pady=1)
        ttk.Button(ex_frame, text="Установить", width=11, command=make_apply(a_i, b_i, k_i)).grid(
            row=i, column=2, padx=4, pady=1
        )

    def clipboard_set(text: str) -> None:
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()

    clip_block_state = {
        "data": None,
        "wrap": None,
        "defactor_bundle": None,
        "omit_raw_decomposition": False,
        "between_tail_lines": None,
        "nines_probe_eligible": None,  # (a, b₀, k): девятки в b₀, |L|=|R|≤26
        "param_btn": None,
    }

    def copy_between_separators() -> None:
        d = clip_block_state["data"]
        w = clip_block_state["wrap"]
        if d is None or w is None:
            messagebox.showinfo(
                "Нет блока",
                "Сначала выполните полный расчёт (без режима «только число»), "
                "чтобы появился текст между линиями из знаков =.",
            )
            return
        clipboard_set(
            between_separators_one_line(
                d,
                w,
                clip_block_state.get("defactor_bundle"),
                clip_block_state.get("omit_raw_decomposition", False),
                clip_block_state.get("between_tail_lines"),
            )
        )

    out_wrap = ttk.Frame(frm)
    out_wrap.grid(row=9, column=0, columnspan=2, sticky="nsew", pady=(4, 0))
    out_wrap.rowconfigure(1, weight=1)
    out_wrap.columnconfigure(0, weight=1)

    out_top = ttk.Frame(out_wrap)
    out_top.grid(row=0, column=0, sticky="ew")
    ttk.Label(out_top, text="Результат").pack(side=tk.LEFT)

    text_holder = ttk.Frame(out_wrap)
    text_holder.grid(row=1, column=0, sticky="nsew")
    text_holder.rowconfigure(0, weight=1)
    text_holder.columnconfigure(0, weight=1)

    v_scroll = ttk.Scrollbar(text_holder, orient=tk.VERTICAL)
    h_scroll = ttk.Scrollbar(text_holder, orient=tk.HORIZONTAL)
    tw = tk.Text(
        text_holder,
        height=28,
        width=88,
        font=("Consolas", 10),
        wrap=tk.NONE,
        exportselection=True,
        undo=False,
        xscrollcommand=h_scroll.set,
        yscrollcommand=v_scroll.set,
    )
    v_scroll.config(command=tw.yview)
    h_scroll.config(command=tw.xview)
    tw.grid(row=0, column=0, sticky="nsew")
    v_scroll.grid(row=0, column=1, sticky="ns")
    h_scroll.grid(row=1, column=0, sticky="ew")

    def copy_all_out() -> None:
        clipboard_set(tw.get("1.0", "end-1c"))

    def copy_selection(_event=None):
        if not tw.tag_ranges("sel"):
            return None
        try:
            clipboard_set(tw.get("sel.first", "sel.last"))
        except tk.TclError:
            return None
        return "break"

    for seq in ("<Control-c>", "<Control-C>", "<Control-Insert>"):
        tw.bind(seq, copy_selection)
    tw.bind("<<Copy>>", copy_selection)
    tw.bind("<Button-1>", lambda e: tw.focus_set())

    ctx = tk.Menu(root, tearoff=0)
    ctx.add_command(label="Копировать", command=lambda: copy_selection())

    def show_ctx(event):
        try:
            ctx.tk_popup(event.x_root, event.y_root)
        finally:
            ctx.grab_release()

    tw.bind("<Button-3>", show_ctx)

    # Копировать всё — глиф Copy (Segoe MDL2)
    copy_all_btn = tk.Button(
        out_top,
        text="\uE8C8",
        font=("Segoe MDL2 Assets", 12),
        command=copy_all_out,
        cursor="hand2",
        relief=tk.GROOVE,
        padx=6,
        pady=0,
        takefocus=False,
    )
    copy_all_btn.pack(side=tk.RIGHT, padx=(8, 0))
    # Между === в одну строку (без рубки)
    copy_between_btn = tk.Button(
        out_top,
        text="\u2261",
        font=("Segoe UI Symbol", 12),
        command=copy_between_separators,
        cursor="hand2",
        relief=tk.GROOVE,
        padx=5,
        pady=0,
        takefocus=False,
    )
    copy_between_btn.pack(side=tk.RIGHT, padx=(0, 4))

    def run_parametric_append_for_state(a_st: int, k_st: int) -> None:
        """Добавить блок параметрической формы (кнопка и авто после «Вычислить»)."""
        try:
            root.configure(cursor="watch")
            root.update_idletasks()
            rows = build_parametric_analysis_block(a_st, k_st)
        except ParametricAnalysisError as ex:
            messagebox.showerror("Параметрическая форма", str(ex))
        except Exception:
            messagebox.showerror(
                "Параметрическая форма",
                traceback.format_exc(),
            )
        else:
            insert_parametric_analysis_lines(tw, rows)
            tw.update_idletasks()
            # Красный «крик» внизу — обязательно показать сразу; иначе — к началу текста.
            if parametric_block_has_shout(rows):
                tw.see(tk.END)
            else:
                tw.yview_moveto(0)
        finally:
            root.configure(cursor="")

    def run_compute():
        clip_block_state["nines_probe_eligible"] = None
        pb = clip_block_state.get("param_btn")
        if pb is not None:
            pb.configure(state=tk.DISABLED)
        try:
            a = var_a.get()
            b0 = var_b.get()
            k = var_k.get()
            warn_max = var_warn_max.get()
        except tk.TclError:
            messagebox.showerror("Параметры", "Введите целые числа во все поля.")
            return

        if k < 1:
            messagebox.showerror("Параметры", "k должно быть ≥ 1")
            return
        if a == 0:
            messagebox.showerror("Параметры", "a не должно быть 0")
            return
        if warn_max < 1:
            messagebox.showerror("Параметры", "Порог предупреждения должен быть ≥ 1")
            return

        tw.delete("1.0", tk.END)
        tw.insert(tk.END, "Считаю\n")
        tw.update_idletasks()

        use_styled = False
        text = ""
        header = eq_lines = sep_line = None
        defactor_bundle = None
        full_factor_display = None
        between_tail_lines = None
        clip_block_state["data"] = None
        clip_block_state["wrap"] = None
        clip_block_state["defactor_bundle"] = None
        clip_block_state["omit_raw_decomposition"] = False
        clip_block_state["between_tail_lines"] = None

        try:
            data = compute_ramanujan_decomposition(a, b0, k, factorize=False)
            want_full = not only_count.get()

            if want_full and data["total_terms"] > warn_max:
                ok = messagebox.askyesno(
                    "Большой вывод",
                    (
                        f"Членов в разложении: {data['total_terms']}\n"
                        f"Это больше порога ({warn_max}). Полный вывод и факторизация "
                        f"могут занять заметное время.\n\n"
                        f"Продолжить?"
                    ),
                    icon="warning",
                )
                if not ok:
                    clip_block_state["data"] = None
                    clip_block_state["wrap"] = None
                    clip_block_state["defactor_bundle"] = None
                    clip_block_state["omit_raw_decomposition"] = False
                    clip_block_state["between_tail_lines"] = None
                    tw.delete("1.0", tk.END)
                    tw.insert(
                        tk.END,
                        f"Отменено. Членов было бы: {data['total_terms']} "
                        f"(порог предупреждения: {warn_max}).\n",
                    )
                    return

            if want_full:
                data = {
                    **data,
                    "factor_str": format_factorization(data["total_val"]),
                }

            wrap_w = _estimate_wrap_chars(tw)
            if only_count.get():
                text = build_output(data, True, wrap_width=wrap_w)
            else:
                header, eq_lines, sep_line = build_output_parts(data, wrap_width=wrap_w)
                if var_defactor.get():
                    defactor_bundle = try_defactored_equation_lines(
                        data["L_final"], data["R_final"], wrap_w
                    )
                if var_defactor.get() and defactor_bundle is not None:
                    header = header[:-1]
                    eq_lines = []
                if (
                    defactor_bundle is not None
                    and var_full_factor.get()
                ):
                    _g3, _n, _eq, L2, R2 = defactor_bundle
                    full_factor_display = build_full_factor_display(
                        L2,
                        R2,
                        wrap_w,
                        bases_only=var_bases_only.get(),
                        factor_columns=var_bases_only.get()
                        and var_factor_columns.get(),
                    )
                    between_tail_lines = list(full_factor_display[1])
                use_styled = True
        except Exception:
            use_styled = False
            text = traceback.format_exc()

        tw.delete("1.0", tk.END)
        if use_styled:
            insert_result_with_bold_left_side(
                tw,
                header,
                eq_lines,
                sep_line,
                defactor_bundle,
                full_factor_display,
            )
            tw.update_idletasks()
            tw.yview_moveto(0)
            clip_block_state["data"] = data
            clip_block_state["wrap"] = wrap_w
            clip_block_state["defactor_bundle"] = defactor_bundle
            clip_block_state["omit_raw_decomposition"] = bool(
                var_defactor.get() and defactor_bundle is not None
            )
            clip_block_state["between_tail_lines"] = between_tail_lines
            if parametric_form_eligible_for_last_run(data):
                clip_block_state["nines_probe_eligible"] = (
                    data["a"],
                    data["b_start"],
                    data["k"],
                )
            else:
                clip_block_state["nines_probe_eligible"] = None
            pb2 = clip_block_state.get("param_btn")
            if pb2 is not None:
                pb2.configure(
                    state=tk.NORMAL
                    if clip_block_state["nines_probe_eligible"]
                    else tk.DISABLED
                )
            if (
                var_auto_parametric.get()
                and clip_block_state.get("nines_probe_eligible")
            ):
                a_auto, _, k_auto = clip_block_state["nines_probe_eligible"]
                run_parametric_append_for_state(a_auto, k_auto)
        else:
            tw.insert(tk.END, text)
            tw.update_idletasks()
            tw.yview_moveto(0)

    btn_row = ttk.Frame(frm)
    btn_row.grid(row=8, column=0, columnspan=2, sticky="ew", pady=6)
    btn_row.columnconfigure(0, weight=1)
    btn_left = ttk.Frame(btn_row)
    btn_left.grid(row=0, column=0, sticky="w")
    ttk.Button(btn_left, text="Вычислить", command=run_compute).pack(side=tk.LEFT)
    btn_param = ttk.Button(
        btn_left,
        text="Параметрическая форма",
        state=tk.DISABLED,
        command=lambda: None,
    )
    btn_param.pack(side=tk.LEFT, padx=(10, 0))
    ttk.Checkbutton(
        btn_left,
        text="Сразу параметрическая форма",
        variable=var_auto_parametric,
    ).pack(side=tk.LEFT, padx=(12, 0))
    clip_block_state["param_btn"] = btn_param

    def run_parametric_analysis():
        e = clip_block_state.get("nines_probe_eligible")
        if not e:
            messagebox.showinfo(
                "Параметрическая форма",
                "Сначала выполните «Вычислить» с полным выводом при b₀ из одних девяток "
                "(9, 99, 999, …), при этом число кубов слева и справа должно совпадать и быть "
                f"не больше {PARAMETRIC_MAX_CUBES_PER_SIDE} на сторону.",
            )
            return
        a_st, _b_st, k_st = e
        try:
            cur_a = var_a.get()
            cur_k = var_k.get()
        except tk.TclError:
            messagebox.showerror("Параметры", "Некорректные числа в полях.")
            return
        if cur_a != a_st or cur_k != k_st:
            messagebox.showwarning(
                "Параметры изменились",
                (
                    f"Последний подходящий расчёт был при a = {a_st}, k = {k_st}. "
                    "Верните эти значения или снова нажмите «Вычислить»."
                ),
            )
            return
        run_parametric_append_for_state(a_st, k_st)

    btn_param.configure(command=run_parametric_analysis)

    def open_author_site():
        webbrowser.open(AUTHOR_SITE_URL)

    ttk.Button(btn_row, text="Сайт автора", command=open_author_site).grid(
        row=0, column=1, sticky="e"
    )


    for w in (sp_a, sp_b, sp_k, sp_warn):
        w.bind("<Return>", lambda e: run_compute())
    root.mainloop()


if __name__ == "__main__":
    main()
