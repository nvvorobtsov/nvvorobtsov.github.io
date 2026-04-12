"""
GUI для экспериментов с телескопическим разложением (логика в perl/cmd/clear_result.py).

Запуск из этой папки:
  python decompose_gui.py
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

_ROOT = Path(__file__).resolve().parent.parent
_CMD = _ROOT / "perl" / "cmd"
if str(_CMD) not in sys.path:
    sys.path.insert(0, str(_CMD))

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


def _invariant_fac_tokens_for_columns(fac_str: str) -> list[str]:
    """Токены факторов для таблицы по колонкам; дробь «num / den» делит на части по « / »."""
    s = (fac_str or "").strip()
    if not s:
        return []
    if " / " in s:
        left, right = s.split(" / ", 1)
        return _factor_string_tokens(left) + ["/"] + _factor_string_tokens(right)
    return _factor_string_tokens(s)


def _invariant_P_coef_factor_pairs(
    P: sp.Expr, x_sym: sp.Symbol
) -> list[tuple[str, str]]:
    """Пары (строка коэффициента, строка факторизации) по степеням x от старшей к младшей; нулевые пропускаем."""
    poly = sp.Poly(sp.expand(P), x_sym, domain="QQ")
    pairs = sorted(poly.terms(), key=lambda t: t[0][0], reverse=True)
    out: list[tuple[str, str]] = []
    for (exp,), coef in pairs:
        c = sp.Rational(coef)
        if c == 0:
            continue
        if c.q == 1:
            v = int(c.p)
            if abs(v) <= 1:
                fac = format_factorization(v)
            else:
                fac = format_factorization(abs(v))
        else:
            num, den = int(c.p), int(c.q)
            coef_str = f"{num}/{den}" if den != 1 else str(num)
            fac = f"{format_factorization(abs(num))} / {format_factorization(den)}"
            out.append((coef_str, fac))
            continue
        out.append((str(v), fac))
    return out


def format_invariant_P_factor_table(
    P: sp.Expr,
    x_sym: sp.Symbol,
    *,
    by_columns: bool = False,
) -> tuple[list[str], list[Optional[str]]]:
    """Таблица факторов коэффициентов инвариантного P(x): как у оснований, выравнивание факторов по колонкам — вправо."""
    rows_data = _invariant_P_coef_factor_pairs(P, x_sym)
    if not rows_data:
        return ([], [])
    coef_ints: list[int] = []
    for cs, _fs in rows_data:
        try:
            coef_ints.append(int(cs))
        except ValueError:
            coef_ints.append(0)

    if by_columns:
        factor_rows = [_invariant_fac_tokens_for_columns(f) for _, f in rows_data]
        nf = max((len(fr) for fr in factor_rows), default=0)
        if nf < 1:
            nf = 1
        h_base = "Коэффициент"
        wn = max(len(h_base), max((len(r[0]) for r in rows_data), default=0))
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
        for row_i, ((_n, _f), fr) in enumerate(zip(rows_data, factor_rows)):
            row_line = "| " + _n.rjust(wn) + " |"
            for j, cw in enumerate(col_widths):
                cell = fr[j] if j < len(fr) else ""
                row_line += " " + cell.rjust(cw) + " |"
            out.append(row_line)
            v = coef_ints[row_i] if row_i < len(coef_ints) else 0
            tags.append(
                TAG_PRIME_TABLE_ROW if (v != 0 and _highlight_prime_or_unit_base(abs(v))) else None
            )
        out.append(sep)
        tags.append(None)
        return out, tags

    h0, h1 = "Коэффициент", "Факторизация"
    wn = max(len(h0), max((len(r[0]) for r in rows_data), default=0))
    wf = max(len(h1), max((len(r[1]) for r in rows_data), default=0))
    sep = "+" + "-" * (wn + 2) + "+" + "-" * (wf + 2) + "+"
    out = [
        sep,
        "| " + h0.rjust(wn) + " | " + h1.ljust(wf) + " |",
        sep,
    ]
    tags: list[Optional[str]] = [None, None, None]
    for i, (n, fac) in enumerate(rows_data):
        out.append("| " + n.rjust(wn) + " | " + fac.ljust(wf) + " |")
        v = coef_ints[i] if i < len(coef_ints) else 0
        tags.append(
            TAG_PRIME_TABLE_ROW if (v != 0 and _highlight_prime_or_unit_base(abs(v))) else None
        )
    out.append(sep)
    tags.append(None)
    return out, tags


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
    """Одна строка тождества (как между === в выводе): без переносов и без заголовков блоков.

    При наличии дефакторизации — только сокращённое тождество (N = … = …^3+…), без строки
    про g³ и без заголовка «После дефакторизации…». Иначе — сырое тождество. Хвост с таблицей
    полной факторизации в буфер не попадает.
    """
    _ = omit_raw_decomposition  # API для copy_between_separators; выбор по defactor_bundle
    _ = between_tail_lines
    if defactor_bundle is not None:
        _gcd_line, factor_line, eq_lines, _L2, _R2 = defactor_bundle
        return factor_line.rstrip() + "".join(eq_lines)
    header, eq_lines, _ = build_output_parts(data, wrap_width=wrap_width)
    factor_line = header[-1]
    return factor_line.rstrip() + "".join(eq_lines)


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
        tw.tag_configure(
            TAG_PRIME_TABLE_ROW,
            font=(fam, sz, "bold"),
            foreground=TABLE_PRIME_BLUE,
        )
    except tk.TclError:
        tw.tag_configure(
            TAG_PARAMETRIC_SHOUT,
            font=("Consolas", 18, "bold"),
            foreground="#C62828",
        )
        tw.tag_configure(
            TAG_PRIME_TABLE_ROW,
            font=("Consolas", 10, "bold"),
            foreground=TABLE_PRIME_BLUE,
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


def _factor_abs_int_to_str(n: int, *, compact_powers: bool) -> str:
    """Разложение |n| ≥ 1 на простые множители.

    compact_powers=True: 2^3·3^2·7 (верхние индексы у степеней).
    compact_powers=False: 2·2·2·3·3·7 (кратность — повторением основания).
    """
    n = int(abs(n))
    if n < 1:
        return ""
    if n == 1:
        return "1"
    fac = sp.factorint(n)
    parts: list[str] = []
    for p in sorted(fac.keys()):
        e = int(fac[p])
        if compact_powers:
            if e == 1:
                parts.append(str(p))
            else:
                parts.append(str(p) + _superscript_int(e))
        else:
            parts.extend([str(p)] * e)
    return "·".join(parts)


def _format_factored_rational_magnitude(c_abs: sp.Rational, *, compact_powers: bool) -> str:
    """Модуль положительного рационального коэффициента в «простом» виде."""
    c_abs = sp.Rational(c_abs)
    if c_abs.q == 1:
        return _factor_abs_int_to_str(int(c_abs.p), compact_powers=compact_powers)
    num = _factor_abs_int_to_str(int(c_abs.p), compact_powers=compact_powers)
    den = _factor_abs_int_to_str(int(c_abs.q), compact_powers=compact_powers)
    return f"{num}/{den}"


def format_polynomial_line_factorized(
    expr: sp.Expr, x_sym: sp.Symbol, *, x_label: str = "x"
) -> str:
    """Как format_polynomial_line, но все коэффициенты — в виде произведения простых со степенями
    в верхнем индексе (например 3²·x, 2²·3·5·x и 3²·7 у свободного члена)."""
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
            out.append(_format_factored_rational_magnitude(cabs, compact_powers=True))
            continue
        if cabs == 1:
            coef_txt = ""
        else:
            coef_txt = (
                _format_factored_rational_magnitude(cabs, compact_powers=True) + "·"
            )
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


def b0_middle_uniform_for_parametric(b0: int) -> bool:
    """b₀ > 2 цифр; после отбрасывания первой и последней цифры средняя часть — только «9» или только «0».

    Короткие b₀ с такой серединой (например 290) намеренно допускаются: те же крайние цифры и однородное
    «ядро» задают семейство «телескопируемого» масштаба (290, 2990, 29990, …), а три пробы b₀ при
    длинах 7/6/5 цифр фиксируют три точки для интерполяции по x = 10⁷, 10⁶, 10⁵.
    """
    if b0 <= 0:
        return False
    s = str(b0)
    if len(s) <= 2:
        return False
    mid = s[1:-1]
    if not mid:
        return False
    return len(set(mid)) == 1 and mid[0] in ("0", "9")


def b0_parametric_probe_eligible(b0: int) -> bool:
    """Условие на b₀ для параметрической формы: все девятки или однородное «среднее» (только 0 или только 9)."""
    return b0_is_all_nines(b0) or b0_middle_uniform_for_parametric(b0)


def parametric_probe_b0_triple(b0_template: int) -> tuple[int, int, int]:
    """Три значения b₀ для масштабов 10⁷, 10⁶, 10⁵ (высокая → низкая проба).

    Классика (все девятки): 10⁷−1, 10⁶−1, 10⁵−1.
    Иначе: первая и последняя цифры как у b₀_template, среднее — (T−2) одинаковых цифр c (та же, что в «середине»
    исходного b₀), для T = 7, 6, 5 (например 192 → 1999992, 199992, 19992).
    """
    b0_template = int(b0_template)
    if b0_template <= 0:
        raise ValueError("b0_template must be positive")
    if b0_is_all_nines(b0_template):
        return (10**7 - 1, 10**6 - 1, 10**5 - 1)
    s = str(b0_template)
    if len(s) <= 2 or not b0_middle_uniform_for_parametric(b0_template):
        raise ValueError("b0_template does not match parametric mask")
    mid = s[1:-1]
    c = mid[0]
    f, lch = s[0], s[-1]
    out: list[int] = []
    for total_digits in (7, 6, 5):
        m = total_digits - 2
        out.append(int(f + c * m + lch))
    return (out[0], out[1], out[2])


# Имена оснований в блоке параметрической формы — a…z (не более 26 кубов на сторону).
PARAMETRIC_MAX_CUBES_PER_SIDE = 26


def parametric_form_eligible_for_last_run(data: dict) -> bool:
    """Условия активации кнопки «Параметрическая форма» по данным последнего полного расчёта."""
    if not b0_parametric_probe_eligible(data["b_start"]):
        return False
    Ld, Rd = order_sides_for_display(data["L_final"], data["R_final"])
    nL, nR = len(Ld), len(Rd)
    if nL != nR:
        return False
    return 1 <= nL <= PARAMETRIC_MAX_CUBES_PER_SIDE


# Три масштаба интерполяции по x = 10⁷, 10⁶, 10⁵; соответствующие b₀ — из parametric_probe_b0_triple.
_PARAMETRIC_X_EXPONENTS = (7, 6, 5)


def _sorted_display_sides(
    a: int, k: int, b0_probe: int
) -> tuple[list[int], list[int]]:
    data = compute_ramanujan_decomposition(a, b0_probe, k, factorize=False)
    Ld, Rd = order_sides_for_display(data["L_final"], data["R_final"])
    return sorted(int(x) for x in Ld), sorted(int(x) for x in Rd)


def build_parametric_analysis_block(
    a: int,
    k: int,
    b0_template: int,
    *,
    show_p_factor_table: bool = False,
    p_factor_by_columns: bool = False,
    s12_factorized: bool = False,
) -> list[tuple[str, Optional[str]]]:
    """Строки блока параметрической формы; (текст, TAG_PARAMETRIC_SHOUT) для редких сумм/сумм квадратов."""
    b_hi, b_mid, b_lo = parametric_probe_b0_triple(b0_template)
    sides: list[tuple[list[int], list[int]]] = [
        _sorted_display_sides(a, k, b_hi),
        _sorted_display_sides(a, k, b_mid),
        _sorted_display_sides(a, k, b_lo),
    ]
    n_hi, n_mid, n_lo = _PARAMETRIC_X_EXPONENTS
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
                "Число кубов на сторонах меняется при переходе между пробами b₀; "
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
                f"Проверка на средней пробе b₀ = {b_mid}: значения S1 не совпали с вычислением."
            )
    for idx, p in enumerate(R_polys):
        if int(p.subs(x_sym, x_mid)) != sides[1][1][idx]:
            raise ParametricAnalysisError(
                f"Проверка на средней пробе b₀ = {b_mid}: значения S2 не совпали с вычислением."
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
            "— Параметрическая форма (три расчёта при пробах b₀ для масштабов 10⁷, 10⁶, 10⁵; "
            f"пробы: {b_hi}, {b_mid}, {b_lo}; согласованность проверяется при b₀ = {b_mid}) —",
            None,
        ),
        (
            f"a = {a},  k = {k}   (интерполяция по x = 10⁷, 10⁶, 10⁵; подставляйте x = 10ⁿ согласно масштабу)",
            None,
        ),
        ("", None),
        ("Группа S1 — основания кубов слева от «=» (квадратики по x)", None),
    ]
    _fmt_poly = (
        format_polynomial_line_factorized
        if s12_factorized
        else format_polynomial_line
    )
    for i, p in enumerate(L_polys):
        rows.append((f"{_name(i)}₁ = {_fmt_poly(p, x_sym)}", None))
    rows.append(("", None))
    rows.append(
        ("Группа S2 — основания кубов справа от «=» (квадратики по x)", None),
    )
    for i, p in enumerate(R_polys):
        rows.append((f"{_name(i)}₂ = {_fmt_poly(p, x_sym)}", None))
    rows.append(("", None))
    rows.append(
        ("Инвариантный многочлен P(x) = Σ S1³ = Σ S2³ (обе стороны)", None),
    )
    rows.append((format_polynomial_line(P, x_sym), None))
    if show_p_factor_table:
        ft_lines, ft_tags = format_invariant_P_factor_table(
            P, x_sym, by_columns=p_factor_by_columns
        )
        if ft_lines:
            rows.append(("", None))
            rows.append(("Таблица факторов коэффициентов P(x):", None))
            for i, ln in enumerate(ft_lines):
                tg = ft_tags[i] if i < len(ft_tags) else None
                rows.append((ln, tg))
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

    outer = ttk.Frame(root, padding=12)
    outer.grid(row=0, column=0, sticky="nsew")
    root.rowconfigure(0, weight=1)
    root.columnconfigure(0, weight=1)
    outer.columnconfigure(0, weight=1)
    outer.rowconfigure(0, weight=0)
    outer.rowconfigure(1, weight=1)

    try:
        _paned_bg = ttk.Style().lookup("TFrame", "background")
    except tk.TclError:
        _paned_bg = ""
    if not _paned_bg:
        _paned_bg = root.cget("bg")

    # Всё выше «Макс. членов…» — вне PanedWindow: шов не затрагивает параметры и галочки.
    head_frm = ttk.Frame(outer)
    head_frm.grid(row=0, column=0, sticky="ew")

    pw = tk.PanedWindow(
        outer,
        orient=tk.VERTICAL,
        sashrelief=tk.GROOVE,
        sashwidth=7,
        sashpad=2,
        bd=0,
        background=_paned_bg,
    )
    pw.grid(row=1, column=0, sticky="nsew")
    # Canvas: иначе PanedWindow не даёт сжать панель ниже winfo_reqheight() детей — шов «липнет».
    split_canvas = tk.Canvas(
        pw,
        bg=_paned_bg,
        highlightthickness=0,
        bd=0,
    )
    inner_split = ttk.Frame(split_canvas)
    _split_inner_win = split_canvas.create_window(0, 0, window=inner_split, anchor="nw")

    def _split_canvas_on_configure(event: tk.Event) -> None:
        if event.widget != split_canvas:
            return
        try:
            w = int(event.width)
            if w > 1:
                split_canvas.itemconfigure(_split_inner_win, width=w)
            # Вертикаль не трогаем: inner_split всегда (0, 0). Шов только уменьшает высоту canvas —
            # обрезка снизу, строка «Макс. членов…» не «ездит» при перетаскивании.
            split_canvas.coords(_split_inner_win, 0, 0)
        except (tk.TclError, ValueError):
            pass

    split_canvas.bind("<Configure>", _split_canvas_on_configure)

    def _split_inner_on_configure(_event: tk.Event) -> None:
        try:
            bb = split_canvas.bbox("all")
            if bb:
                split_canvas.configure(scrollregion=bb)
        except tk.TclError:
            pass

    inner_split.bind("<Configure>", _split_inner_on_configure)

    bottom_frm = tk.Frame(pw, bg=_paned_bg, bd=0, highlightthickness=0)
    # pw.add только после сборки inner_split (порог + «Примеры») и bottom_frm.

    head_frm.columnconfigure(1, weight=1)
    inner_split.columnconfigure(1, weight=1)
    bottom_frm.columnconfigure(0, weight=1)
    bottom_frm.columnconfigure(1, weight=1)
    bottom_frm.rowconfigure(0, weight=0)
    bottom_frm.rowconfigure(1, weight=1)

    var_a = tk.IntVar(value=2)
    var_b = tk.IntVar(value=10)
    var_k = tk.IntVar(value=5)
    var_warn_max = tk.IntVar(value=50000)
    var_auto_parametric = tk.BooleanVar(value=False)
    var_p_factor_table = tk.BooleanVar(value=False)
    var_p_factor_columns = tk.BooleanVar(value=False)
    var_s12_factorized = tk.BooleanVar(value=False)

    ttk.Label(head_frm, text="a:").grid(row=0, column=0, sticky="w", pady=2)
    sp_a = tk.Spinbox(
        head_frm,
        from_=-300,
        to=300,
        increment=1,
        textvariable=var_a,
        width=12,
    )
    sp_a.grid(row=0, column=1, sticky="w", pady=2)

    ttk.Label(head_frm, text="b₀ (начальное b):").grid(row=1, column=0, sticky="w", pady=2)
    sp_b = tk.Spinbox(
        head_frm,
        from_=-20000,
        to=20000,
        increment=1,
        textvariable=var_b,
        width=12,
    )
    sp_b.grid(row=1, column=1, sticky="w", pady=2)

    ttk.Label(head_frm, text="k (число шагов):").grid(row=2, column=0, sticky="w", pady=2)
    sp_k = tk.Spinbox(
        head_frm,
        from_=1,
        to=300000,
        increment=1,
        textvariable=var_k,
        width=12,
    )
    sp_k.grid(row=2, column=1, sticky="w", pady=2)

    only_count = tk.BooleanVar(value=False)
    chk = ttk.Checkbutton(
        head_frm,
        text="Только число членов (без строки разложения)",
        variable=only_count,
    )
    chk.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 4))

    var_defactor = tk.BooleanVar(value=True)
    chk_def = ttk.Checkbutton(
        head_frm,
        text=(
            "Проверка дефакторизации (g³ = (НОД оснований)³, N = факторизация(N) =, сокращённое "
            "тождество; при НОД>1 сырое разложение не показывается; при НОД=1 — полный вывод)"
        ),
        variable=var_defactor,
    )
    chk_def.grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 4))

    var_full_factor = tk.BooleanVar(value=False)
    var_bases_only = tk.BooleanVar(value=True)
    opt_sub = ttk.Frame(head_frm)
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

    warn_lbl = ttk.Label(
        inner_split,
        text=(
            "Макс. членов разложения — предупреждать о большом выводе\n"
            "(только если галочка «только число» выключена):"
        ),
        justify=tk.LEFT,
    )
    warn_lbl.grid(row=0, column=0, sticky="nw", pady=2)
    sp_warn = tk.Spinbox(
        inner_split,
        from_=4,
        to=2_000_000,
        increment=1,
        textvariable=var_warn_max,
        width=12,
    )
    sp_warn.grid(row=0, column=1, sticky="w", pady=2)

    ex_frame = ttk.LabelFrame(
        inner_split, text="Примеры: тройка параметров → число членов (для ориентира)"
    )
    _ex_frame_grid_kw = {
        "row": 1,
        "column": 0,
        "columnspan": 2,
        "sticky": "ew",
        "pady": (10, 6),
    }
    ex_frame.grid(**_ex_frame_grid_kw)
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

    root.update_idletasks()
    ex_frame.grid_remove()
    warn_lbl.grid_remove()
    sp_warn.grid_remove()
    root.update_idletasks()
    # Минимум первой панели: мало пикселей, чтобы шов можно было утащить почти к head_frm.
    _min_split = 6
    warn_lbl.grid(row=0, column=0, sticky="nw", pady=2)
    sp_warn.grid(row=0, column=1, sticky="w", pady=2)
    root.update_idletasks()
    ex_frame.grid(**_ex_frame_grid_kw)
    root.update_idletasks()
    # Стартовая высота первой панели (порог + «Примеры») — по запросу inner_split.
    _split_full_reqh = max(int(inner_split.winfo_reqheight()) + 24, int(_min_split) + 1)

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
        "nines_probe_eligible": None,  # (a, b₀, k): маска b₀ для параметрики, |L|=|R|≤26
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

    out_wrap = ttk.Frame(bottom_frm)
    out_wrap.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(4, 0))
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
        height=14,
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

    def run_parametric_append_for_state(a_st: int, b0_st: int, k_st: int) -> None:
        """Добавить блок параметрической формы (кнопка и авто после «Вычислить»)."""
        try:
            root.configure(cursor="watch")
            root.update_idletasks()
            rows = build_parametric_analysis_block(
                a_st,
                k_st,
                b0_st,
                show_p_factor_table=var_p_factor_table.get(),
                p_factor_by_columns=var_p_factor_table.get()
                and var_p_factor_columns.get(),
                s12_factorized=var_s12_factorized.get(),
            )
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
            # Режим «только число» — по флагу на виджете: на части сборок (Python 3.14 + ttk)
            # BooleanVar.get() и отрисовка чекбокса могут расходиться.
            only_number_mode = "selected" in chk.state()
            want_full = not only_number_mode

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
            if only_number_mode:
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
                a_auto, b0_auto, k_auto = clip_block_state["nines_probe_eligible"]
                run_parametric_append_for_state(a_auto, b0_auto, k_auto)
        else:
            tw.insert(tk.END, text)
            tw.update_idletasks()
            tw.yview_moveto(0)

    btn_row = ttk.Frame(bottom_frm)
    btn_row.grid(row=0, column=0, columnspan=2, sticky="ew", pady=6)
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
    chk_p_factor_table = ttk.Checkbutton(
        btn_left,
        text="Таблица факторов",
        variable=var_p_factor_table,
    )
    chk_p_factor_table.pack(side=tk.LEFT, padx=(12, 0))
    chk_p_factor_columns = ttk.Checkbutton(
        btn_left,
        text="Факторы по колонкам таблицы",
        variable=var_p_factor_columns,
    )
    chk_p_factor_columns.pack(side=tk.LEFT, padx=(8, 0))
    chk_s12_fact = ttk.Checkbutton(
        btn_left,
        text="S1,S2: факторизованный вид",
        variable=var_s12_factorized,
    )
    chk_s12_fact.pack(side=tk.LEFT, padx=(8, 0))

    def _sync_p_factor_column_check(*_args: object) -> None:
        st = tk.NORMAL if var_p_factor_table.get() else tk.DISABLED
        chk_p_factor_columns.configure(state=st)

    var_p_factor_table.trace_add("write", _sync_p_factor_column_check)
    _sync_p_factor_column_check()

    clip_block_state["param_btn"] = btn_param

    def run_parametric_analysis():
        e = clip_block_state.get("nines_probe_eligible")
        if not e:
            messagebox.showinfo(
                "Параметрическая форма",
                "Сначала выполните «Вычислить» с полным выводом, когда b₀ либо состоит из одних "
                "девяток (9, 99, 999, …), либо имеет более двух цифр и «середина» (без первой и "
                "последней цифры) — только девятки или только нули (например 192, 2995, 101, "
                "3000000006). Число кубов слева и справа должно совпадать и быть не больше "
                f"{PARAMETRIC_MAX_CUBES_PER_SIDE} на сторону.",
            )
            return
        a_st, b_st, k_st = e
        try:
            cur_a = var_a.get()
            cur_b = var_b.get()
            cur_k = var_k.get()
        except tk.TclError:
            messagebox.showerror("Параметры", "Некорректные числа в полях.")
            return
        if cur_a != a_st or cur_b != b_st or cur_k != k_st:
            messagebox.showwarning(
                "Параметры изменились",
                (
                    f"Последний подходящий расчёт был при a = {a_st}, b₀ = {b_st}, k = {k_st}. "
                    "Верните эти значения или снова нажмите «Вычислить»."
                ),
            )
            return
        run_parametric_append_for_state(a_st, b_st, k_st)

    btn_param.configure(command=run_parametric_analysis)

    def open_author_site():
        webbrowser.open(AUTHOR_SITE_URL)

    ttk.Button(btn_row, text="Сайт автора", command=open_author_site).grid(
        row=0, column=1, sticky="e"
    )

    for w in (sp_a, sp_b, sp_k, sp_warn):
        w.bind("<Return>", lambda e: run_compute())

    pw.add(split_canvas, minsize=int(_min_split), sticky="nsew")
    pw.add(bottom_frm, minsize=200, sticky="nsew")
    root.update_idletasks()
    root.update()
    try:
        ph = max(
            int(pw.winfo_height()),
            int(outer.winfo_height()),
            max(0, int(root.winfo_height()) - 48),
        )
        bottom_min = 200
        want_split = int(_split_full_reqh)
        room = max(ph - bottom_min, int(_min_split))
        target = min(want_split, room)
        target = max(int(target), int(_min_split))
        pw.paneconfigure(split_canvas, minsize=int(_min_split))
        # В части сборок Python у tk.PanedWindow нет sashpos — только sash_place(index, x, y).
        pw.sash_place(0, 0, int(target))
    except tk.TclError:
        pass

    root.mainloop()


if __name__ == "__main__":
    main()
