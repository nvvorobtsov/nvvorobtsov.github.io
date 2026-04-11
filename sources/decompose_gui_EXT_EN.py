"""
GUI: Ramanujan telescopic cube decomposition + parametric form (quadratics in x; see publication 06).
Keep clear_result.py in the same folder (in decompose_gui_EXT_windows.zip or from publication 5).

Run:
  python decompose_gui_EXT_EN.py
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
    try_defactored_equation_lines,
    wrap_equation_lines,
)

AUTHOR_SITE_URL = "https://nvvorobtsov.github.io/"

# Заголовок блока: g — НОД всех оснований кубов до деления; сокращение на g даёт тождество для суммы, делённой на g³.
DEFACTOR_SECTION_TITLE = "After defactorization (g³ — cube of gcd of all bases):"

TITLE_FACTORED_CUBES = "With full factorization of the reduced identity*:"
TITLE_FACTORED_TABLE = "Or: factorizations of the bases only*:"
FOOTNOTE_DEFACT_REDUCED = "* The reduced identity after defactorization."

TAG_PRIME_TABLE_ROW = "prime_table_row"
TABLE_PRIME_BLUE = "#1565C0"


def en_cubes_phrase(n: int) -> str:
    """English count + 'cube' / 'cubes'."""
    n = abs(int(n))
    if n == 1:
        return "1 cube"
    return f"{n} cubes"



def _highlight_prime_or_unit_base(x) -> bool:
    """Highlight row: prime base or 1 (no nontrivial factorization for 1)."""
    v = abs(int(x))
    if v == 1:
        return True
    return v >= 2 and bool(sp.isprime(v))


def _actual_text_widget(st: tk.Widget) -> tk.Text:
    """ScrolledText may expose Text as self or child — depends on Python."""
    inner = getattr(st, "text", None)
    if isinstance(inner, tk.Text):
        return inner
    if isinstance(st, tk.Text):
        return st
    for ch in st.winfo_children():
        if isinstance(ch, tk.Text):
            return ch
    return st  # nonstandard wrapper fallback


def _estimate_wrap_chars(text_w: tk.Widget) -> int:
    """Monospace chars that fit the widget width (for wrapping)."""
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


# (a, b₀, k, term count) — with b₀=0 and these a,k, left of «=» is one cube, right is the rest, no leading «-»
PRESET_EXAMPLES = [
    (50, 0, 4, 10),
    (50, 0, 49, 100),
    (50, 0, 499, 1000),
    (50, 0, 4999, 10000),
    (50, 0, 24999, 50000),
    (50, 0, 49999, 100000),
    (100, 0, 249999, 500000),
]

PRESET_TARGETS_EN = [
    "~10 terms, left: 1 cube",
    "~100, left: 1 cube",
    "~1000, left: 1 cube",
    "~10000, left: 1 cube",
    "~50000, left: 1 cube",
    "~100000, left: 1 cube",
    "~500000, left: 1 cube (a=100)",
]


def build_output_parts(data: dict, *, wrap_width: int = 72):
    """Full output: header, identity lines (wrap), bottom = bar."""
    bar_w = min(max(wrap_width, 40), 200)
    sep = "=" * bar_w
    Ld, Rd = order_sides_for_display(data["L_final"], data["R_final"])
    header = [
        (
            f"Decomposition: a = {data['a']}, b₀ = {data['b_start']}, k = {data['k']}"
        ),
        f"Parameters built. Number of terms in the sequence: {data['total_terms']}.",
        "",
        "Result:",
        f"Left: {en_cubes_phrase(len(Ld))}",
        f"Right: {en_cubes_phrase(len(Rd))}",
        sep,
        f"{data['total_val']} = {data['factor_str']} =",
    ]
    eq_lines = wrap_equation_lines(Ld, Rd, wrap_width)
    return header, eq_lines, sep


def wrap_factored_cube_equation(L: list, R: list, width: int) -> list:
    """Identity lines (like wrap_equation_lines) with fully factored bases in parentheses."""
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
    """Table: integer base | format_factorization layout (monospace).

    Second list — per-line tags (None or TAG_PRIME_TABLE_ROW for data rows with a prime base).
    """
    bases_order = [int(x) for x in L] + [int(x) for x in R]
    rows = []
    for x in L:
        rows.append((str(int(x)), format_factorization(x)))
    for x in R:
        rows.append((str(int(x)), format_factorization(x)))
    h0, h1 = "Base", "Factorization"
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
    """Factor tokens for column layout; fraction «num / den» splits on « / »."""
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
    """Pairs (coefficient string, factorization string) by powers of x high to low; skip zeros."""
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
    """Factor table for invariant P(x) coefficients: like bases, factor tokens in columns — right-aligned."""
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
        h_base = "Coefficient"
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

    h0, h1 = "Coefficient", "Factorization"
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
    h_base: str = "Base",
) -> tuple[list[str], list[Optional[str]]]:
    """Table: base | factor 1 | factor 2 | … (monospace, factor cells right-aligned).

    Second list — per-line tags (same as format_bases_factor_table).
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
    """(mode, lines, line_tags): line_tags aligned with lines, or None for cubes mode."""
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
    """Single-line identity (as between === in the output): no line breaks, no block headers.

    If defactorization is present — only the reduced identity (N = … = …^3+…), without the
    g³ line and without the “After defactorization…” title. Otherwise — the raw identity.
    The tail with the full-factorization table is not included in the clipboard buffer.
    """
    _ = omit_raw_decomposition  # API for copy_between_separators; choice via defactor_bundle
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
            f"Terms in decomposition (after reductions): {data['total_terms']}\n"
            f"Left: {en_cubes_phrase(len(Ld))}\n"
            f"Right: {en_cubes_phrase(len(Rd))}\n"
        )
    h, e, s = build_output_parts(data, wrap_width=wrap_width)
    return "\n".join(h + e + [s])


class ParametricAnalysisError(Exception):
    """Failed to recover quadratics in x = 10ⁿ for b₀ = 10ⁿ − 1."""


# Rare identities Σ S1 = Σ S2 / Σ S1² = Σ S2² — large red bold text in the result pane.
TAG_PARAMETRIC_SHOUT = "parametric_shout"


def parametric_block_has_shout(rows: list[tuple[str, Optional[str]]]) -> bool:
    return any(tag == TAG_PARAMETRIC_SHOUT for _, tag in rows if tag)


def insert_parametric_analysis_lines(
    tw: tk.Text, rows: list[tuple[str, Optional[str]]]
) -> None:
    """Insert parametric block; lines with TAG_PARAMETRIC_SHOUT are the “shout”."""
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
    """One line: polynomial over ℚ in x (Unicode exponents)."""
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


# Parametric block base names — a…z (at most 26 cubes per side).
PARAMETRIC_MAX_CUBES_PER_SIDE = 26


def parametric_form_eligible_for_last_run(data: dict) -> bool:
    """When the «Parametric form» button may activate from the last full run."""
    if not b0_is_all_nines(data["b_start"]):
        return False
    Ld, Rd = order_sides_for_display(data["L_final"], data["R_final"])
    nL, nR = len(Ld), len(Rd)
    if nL != nR:
        return False
    return 1 <= nL <= PARAMETRIC_MAX_CUBES_PER_SIDE


# Three scales: x = 10⁷, 10⁶, 10⁵ with b₀ = 10ⁿ − 1 (internal; UI check at n=6).
_PARAMETRIC_N_DIGITS = (7, 6, 5)


def _sorted_display_sides(
    a: int, k: int, n_digits: int
) -> tuple[list[int], list[int]]:
    b0 = 10**n_digits - 1
    data = compute_ramanujan_decomposition(a, b0, k, factorize=False)
    Ld, Rd = order_sides_for_display(data["L_final"], data["R_final"])
    return sorted(int(x) for x in Ld), sorted(int(x) for x in Rd)


def build_parametric_analysis_block(
    a: int,
    k: int,
    *,
    show_p_factor_table: bool = False,
    p_factor_by_columns: bool = False,
) -> list[tuple[str, Optional[str]]]:
    """Lines for the parametric block; TAG_PARAMETRIC_SHOUT marks rare linear/quadratic sum identities."""
    sides: list[tuple[list[int], list[int]]] = []
    for n in _PARAMETRIC_N_DIGITS:
        sides.append(_sorted_display_sides(a, k, n))
    n_hi, n_mid, n_lo = _PARAMETRIC_N_DIGITS
    x_hi, x_mid, x_lo = 10**n_hi, 10**n_mid, 10**n_lo
    L0, R0 = sides[0]
    if len(L0) != len(R0):
        raise ParametricAnalysisError(
            "Left and right cube counts differ; parametric form unavailable."
        )
    if len(L0) > PARAMETRIC_MAX_CUBES_PER_SIDE:
        raise ParametricAnalysisError(
            f"Too many cubes on one side (limit {PARAMETRIC_MAX_CUBES_PER_SIDE})."
        )
    for i in (1, 2):
        Li, Ri = sides[i]
        if len(Li) != len(L0) or len(Ri) != len(R0):
            raise ParametricAnalysisError(
                "Cube counts change with b₀ scale (10ⁿ−1); "
                "index matching is impossible."
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
            raise ParametricAnalysisError("Left: recovered polynomial degree > 2.")
        L_polys.append(pl)
    for idx in range(len(R0)):
        pts_r = [
            (x_hi, sp.Integer(sides[0][1][idx])),
            (x_mid, sp.Integer(sides[1][1][idx])),
            (x_lo, sp.Integer(sides[2][1][idx])),
        ]
        pr = sp.expand(sp.interpolate(pts_r, x_sym))
        if sp.degree(pr, x_sym) > 2:
            raise ParametricAnalysisError("Right: recovered polynomial degree > 2.")
        R_polys.append(pr)
    for idx, p in enumerate(L_polys):
        if int(p.subs(x_sym, x_mid)) != sides[1][0][idx]:
            raise ParametricAnalysisError(
                "Check b₀ = 10⁶−1: S1 values do not match computation."
            )
    for idx, p in enumerate(R_polys):
        if int(p.subs(x_sym, x_mid)) != sides[1][1][idx]:
            raise ParametricAnalysisError(
                "Check b₀ = 10⁶−1: S2 values do not match computation."
            )
    sum_L3 = sp.expand(sum(p**3 for p in L_polys))
    sum_R3 = sp.expand(sum(p**3 for p in R_polys))
    if sp.expand(sum_L3 - sum_R3) != 0:
        raise ParametricAnalysisError("Cube sums of S1 and S2 polynomials do not match.")
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
            "— Parametric form (internal runs at b₀ = 10⁷−1, 10⁶−1, 10⁵−1; "
            "checked at b₀ = 10⁶−1) —",
            None,
        ),
        (
            f"a = {a},  k = {k}   (x is a power of 10: for b₀ = 10ⁿ−1 substitute x = 10ⁿ)",
            None,
        ),
        ("", None),
        ("Group S1 — cube bases left of «=» (quadratics in x)", None),
    ]
    for i, p in enumerate(L_polys):
        rows.append((f"{_name(i)}₁ = {format_polynomial_line(p, x_sym)}", None))
    rows.append(("", None))
    rows.append(
        ("Group S2 — cube bases right of «=» (quadratics in x)", None),
    )
    for i, p in enumerate(R_polys):
        rows.append((f"{_name(i)}₂ = {format_polynomial_line(p, x_sym)}", None))
    rows.append(("", None))
    rows.append(
        ("Invariant polynomial P(x) = Σ S1³ = Σ S2³ (both sides)", None),
    )
    rows.append((format_polynomial_line(P, x_sym), None))
    if show_p_factor_table:
        ft_lines, ft_tags = format_invariant_P_factor_table(
            P, x_sym, by_columns=p_factor_by_columns
        )
        if ft_lines:
            rows.append(("", None))
            rows.append(("Factor table for coefficients of P(x):", None))
            for i, ln in enumerate(ft_lines):
                tg = ft_tags[i] if i < len(ft_tags) else None
                rows.append((ln, tg))
    rows.append(("", None))
    rows.append(("Extra identities on sums (not cubes):", None))
    if lin_ok:
        rows.append(
            (
                "!!! ATTENTION !!!  Σ S1 = Σ S2  — IDENTITY HOLDS  —  UNUSUAL !!!",
                TAG_PARAMETRIC_SHOUT,
            ),
        )
    else:
        rows.append(("Σ S1 = Σ S2  — does not hold.", None))
    if sq_ok:
        rows.append(
            (
                "!!! ATTENTION !!!  Σ S1² = Σ S2²  — IDENTITY HOLDS  —  UNUSUAL !!!",
                TAG_PARAMETRIC_SHOUT,
            ),
        )
    else:
        rows.append(("Σ S1² = Σ S2² — does not hold.", None))
    return rows


def _insert_eq_lines_bold_left(tw: tk.Text, lines: list, tag: str) -> None:
    """Left of the first « = » in bold (tag)."""
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
    """In identity lines, left of the first « = » is bold blue (#1565C0)."""
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
    root.title("Ramanujan decomposition — a, b₀, k (+ parametric form)")
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

    ttk.Label(head_frm, text="b₀ (initial b):").grid(row=1, column=0, sticky="w", pady=2)
    sp_b = tk.Spinbox(
        head_frm,
        from_=-20000,
        to=20000,
        increment=1,
        textvariable=var_b,
        width=12,
    )
    sp_b.grid(row=1, column=1, sticky="w", pady=2)

    ttk.Label(head_frm, text="k (number of steps):").grid(row=2, column=0, sticky="w", pady=2)
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
        text="Term count only (no decomposition lines)",
        variable=only_count,
    )
    chk.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 4))

    var_defactor = tk.BooleanVar(value=True)
    chk_def = ttk.Checkbutton(
        head_frm,
        text=(
            "Defactorization check (g³ = (gcd of bases)³, N = factorization(N) =, reduced "
            "identity; if gcd>1 raw decomposition is hidden; if gcd=1 — full output)"
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
            "Full factorization of reduced identity (cubes with factored bases; "
            "extra block below defactorization)"
        ),
        variable=var_full_factor,
    )
    chk_ff.pack(side=tk.LEFT)
    chk_bo = ttk.Checkbutton(
        opt_sub,
        text="Bases only (table, no ^3)",
        variable=var_bases_only,
    )
    chk_bo.pack(side=tk.LEFT, padx=(18, 0))

    var_factor_columns = tk.BooleanVar(value=False)
    chk_fc = ttk.Checkbutton(
        opt_sub,
        text="Factors in separate table columns",
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
            "Max decomposition terms — warn if output is large\n"
            "(only when «term count only» is unchecked):"
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
        inner_split, text="Examples: parameter triple → term count (reference)"
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

    ttk.Label(ex_frame, text="Parameters a, b₀, k").grid(row=0, column=0, sticky="w", padx=4, pady=2)
    ttk.Label(ex_frame, text="Terms").grid(row=0, column=1, sticky="w", padx=4, pady=2)
    ttk.Label(ex_frame, text="").grid(row=0, column=2, padx=2, pady=2)

    def make_apply(a_i, b_i, k_i):
        def _apply():
            var_a.set(a_i)
            var_b.set(b_i)
            var_k.set(k_i)

        return _apply

    for i, ((a_i, b_i, k_i, cnt), hint) in enumerate(
        zip(PRESET_EXAMPLES, PRESET_TARGETS_EN), start=1
    ):
        param_txt = f"a = {a_i},  b₀ = {b_i},  k = {k_i}"
        row_txt = f"{param_txt}   ({hint})"
        ttk.Label(ex_frame, text=row_txt).grid(row=i, column=0, sticky="w", padx=4, pady=1)
        ttk.Label(ex_frame, text=str(cnt)).grid(row=i, column=1, sticky="e", padx=8, pady=1)
        ttk.Button(ex_frame, text="Apply", width=11, command=make_apply(a_i, b_i, k_i)).grid(
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
        "nines_probe_eligible": None,  # (a, b₀, k): nines in b₀, |L|=|R|≤26
        "param_btn": None,
    }

    def copy_between_separators() -> None:
        d = clip_block_state["data"]
        w = clip_block_state["wrap"]
        if d is None or w is None:
            messagebox.showinfo(
                "No block",
                "Run a full computation first (without «term count only») "
                "so text between the = bars is available.",
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
    ttk.Label(out_top, text="Result").pack(side=tk.LEFT)

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
    ctx.add_command(label="Copy", command=lambda: copy_selection())

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
        """Append parametric block (button and auto after «Compute»)."""
        try:
            root.configure(cursor="watch")
            root.update_idletasks()
            rows = build_parametric_analysis_block(
                a_st,
                k_st,
                show_p_factor_table=var_p_factor_table.get(),
                p_factor_by_columns=var_p_factor_table.get()
                and var_p_factor_columns.get(),
            )
        except ParametricAnalysisError as ex:
            messagebox.showerror("Parametric form", str(ex))
        except Exception:
            messagebox.showerror(
                "Parametric form",
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
            messagebox.showerror("Parameters", "Enter integers in all fields.")
            return

        if k < 1:
            messagebox.showerror("Parameters", "k must be ≥ 1")
            return
        if a == 0:
            messagebox.showerror("Parameters", "a must not be 0")
            return
        if warn_max < 1:
            messagebox.showerror("Parameters", "Warning threshold must be ≥ 1")
            return

        tw.delete("1.0", tk.END)
        tw.insert(tk.END, "Computing…\n")
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
                    "Large output",
                    (
                        f"Terms in decomposition: {data['total_terms']}\n"
                        f"This exceeds the threshold ({warn_max}). Full output and factorization "
                        f"may take a while.\n\n"
                        f"Continue?"
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
                        f"Cancelled. Would have been {data['total_terms']} terms "
                        f"(warning threshold: {warn_max}).\n",
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
                        data["L_final"], data["R_final"], wrap_w, lang="en"
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

    btn_row = ttk.Frame(bottom_frm)
    btn_row.grid(row=0, column=0, columnspan=2, sticky="ew", pady=6)
    btn_row.columnconfigure(0, weight=1)
    btn_left = ttk.Frame(btn_row)
    btn_left.grid(row=0, column=0, sticky="w")
    ttk.Button(btn_left, text="Compute", command=run_compute).pack(side=tk.LEFT)
    btn_param = ttk.Button(
        btn_left,
        text="Parametric form",
        state=tk.DISABLED,
        command=lambda: None,
    )
    btn_param.pack(side=tk.LEFT, padx=(10, 0))
    ttk.Checkbutton(
        btn_left,
        text="Auto-append parametric form",
        variable=var_auto_parametric,
    ).pack(side=tk.LEFT, padx=(12, 0))
    chk_p_factor_table = ttk.Checkbutton(
        btn_left,
        text="Factor table",
        variable=var_p_factor_table,
    )
    chk_p_factor_table.pack(side=tk.LEFT, padx=(12, 0))
    chk_p_factor_columns = ttk.Checkbutton(
        btn_left,
        text="Factors in separate table columns",
        variable=var_p_factor_columns,
    )
    chk_p_factor_columns.pack(side=tk.LEFT, padx=(8, 0))

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
                "Parametric form",
                "Run «Compute» with full output first, with b₀ all nines (9, 99, 999, …); "
                "left and right cube counts must match and be at most "
                f"{PARAMETRIC_MAX_CUBES_PER_SIDE} per side.",
            )
            return
        a_st, _b_st, k_st = e
        try:
            cur_a = var_a.get()
            cur_k = var_k.get()
        except tk.TclError:
            messagebox.showerror("Parameters", "Invalid numbers in fields.")
            return
        if cur_a != a_st or cur_k != k_st:
            messagebox.showwarning(
                "Parameters changed",
                (
                    f"The last eligible run used a = {a_st}, k = {k_st}. "
                    "Restore those values or press «Compute» again."
                ),
            )
            return
        run_parametric_append_for_state(a_st, k_st)

    btn_param.configure(command=run_parametric_analysis)

    def open_author_site():
        webbrowser.open(AUTHOR_SITE_URL)

    ttk.Button(btn_row, text="Author site", command=open_author_site).grid(
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
