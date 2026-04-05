"""
GUI for Ramanujan telescopic cube decomposition experiments.
Place clear_result.py in the same folder (download both from publication 5 on the site).

Run:
  python decompose_gui_EN.py
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

# g = gcd of all bases before division; factoring out g from each base divides the cube sum by g³.
DEFACTOR_SECTION_TITLE = "After defactorization (g³ — cube of gcd of all bases):"

TITLE_FACTORED_CUBES = "With full factorization of the reduced identity*:"
TITLE_FACTORED_TABLE = "Or: factorizations of the bases only*:"
FOOTNOTE_DEFACT_REDUCED = "* The reduced identity after defactorization."

TAG_PRIME_TABLE_ROW = "prime_table_row"
TABLE_PRIME_BLUE = "#1565C0"


def _highlight_prime_or_unit_base(x) -> bool:
    """Highlight table row: prime base or 1 (no nontrivial factorization)."""
    v = abs(int(x))
    if v == 1:
        return True
    return v >= 2 and bool(sp.isprime(v))


def en_cubes_phrase(n: int) -> str:
    """English count + 'cube' / 'cubes'."""
    n = abs(int(n))
    if n == 1:
        return "1 cube"
    return f"{n} cubes"


def _actual_text_widget(st: tk.Widget) -> tk.Text:
    """ScrolledText may expose the inner Text as self or as a child, depending on Python version."""
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
    """Approximate monospace character count that fits the widget width (for line wrapping)."""
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


# (a, b₀, k, term count) — with b₀=0 and these a,k, one cube on the left of «=», the rest on the right, no «-»
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
    """Full output: header, wrapped equation lines, bottom bar of =."""
    bar_w = min(max(wrap_width, 40), 200)
    sep = "=" * bar_w
    Ld, Rd = order_sides_for_display(data["L_final"], data["R_final"])
    header = [
        (
            f"Decomposition: a = {data['a']}, b₀ = {data['b_start']}, k = {data['k']}"
        ),
        f"Parameters set. Number of terms in the sequence: {data['total_terms']}.",
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
    """Equation lines (like wrap_equation_lines) with fully factored bases in parentheses."""
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
    """Table: integer base | format_factorization (monospace).

    Second list: per-line tags (None or TAG_PRIME_TABLE_ROW for data rows with prime base).
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
        tags.append(TAG_PRIME_TABLE_ROW if _base_is_prime(bases_order[i]) else None)
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
    h_base: str = "Base",
) -> tuple[list[str], list[Optional[str]]]:
    """Table: base | factor 1 | factor 2 | … (monospace, factor cells right-aligned).

    Second list: per-line tags (same convention as format_bases_factor_table).
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
    """Text between === lines without wrapping (single logical line) for clipboard copy."""
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
            f"Terms in decomposition (after reductions): {data['total_terms']}\n"
            f"Left: {en_cubes_phrase(len(Ld))}\n"
            f"Right: {en_cubes_phrase(len(Rd))}\n"
        )
    h, e, s = build_output_parts(data, wrap_width=wrap_width)
    return "\n".join(h + e + [s])


def _insert_eq_lines_bold_left(tw: tk.Text, lines: list, tag: str) -> None:
    """Left-hand side up to first « = » in bold (tag)."""
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
    """In equation lines, left side up to first « = » is bold blue (#1565C0)."""
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
    root.title("Ramanujan decomposition — parameters a, b₀, k")
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

    ttk.Label(frm, text="b₀ (initial b):").grid(row=1, column=0, sticky="w", pady=2)
    sp_b = tk.Spinbox(
        frm,
        from_=-20000,
        to=20000,
        increment=1,
        textvariable=var_b,
        width=12,
    )
    sp_b.grid(row=1, column=1, sticky="w", pady=2)

    ttk.Label(frm, text="k (number of steps):").grid(row=2, column=0, sticky="w", pady=2)
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
        text="Term count only (no decomposition lines)",
        variable=only_count,
    )
    chk.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 4))

    var_defactor = tk.BooleanVar(value=True)
    chk_def = ttk.Checkbutton(
        frm,
        text=(
            "Defactorization check (g³ = (gcd of bases)³, N = factorization(N) =, reduced "
            "identity; if gcd>1 the raw decomposition is hidden; if gcd=1 — full output)"
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

    ttk.Label(
        frm,
        text=(
            "Max decomposition terms — warn if output is large\n"
            "(only when «term count only» is unchecked):"
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

    ex_frame = ttk.LabelFrame(frm, text="Examples: parameter triple → term count (reference)")
    ex_frame.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(10, 6))
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

    out_wrap = ttk.Frame(frm)
    out_wrap.grid(row=9, column=0, columnspan=2, sticky="nsew", pady=(4, 0))
    out_wrap.rowconfigure(1, weight=1)
    out_wrap.columnconfigure(0, weight=1)

    out_top = ttk.Frame(out_wrap)
    out_top.grid(row=0, column=0, sticky="ew")
    ttk.Label(out_top, text="Output").pack(side=tk.LEFT)

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
    ctx.add_command(label="Copy", command=lambda: copy_selection())

    def show_ctx(event):
        try:
            ctx.tk_popup(event.x_root, event.y_root)
        finally:
            ctx.grab_release()

    tw.bind("<Button-3>", show_ctx)

    # Copy all — Copy glyph (Segoe MDL2)
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
    # Between === as one line (no wrap)
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

    def run_compute():
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
            want_full = not only_count.get()

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
            if only_count.get():
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
            clip_block_state["data"] = data
            clip_block_state["wrap"] = wrap_w
            clip_block_state["defactor_bundle"] = defactor_bundle
            clip_block_state["omit_raw_decomposition"] = bool(
                var_defactor.get() and defactor_bundle is not None
            )
            clip_block_state["between_tail_lines"] = between_tail_lines
        else:
            tw.insert(tk.END, text)

    btn_row = ttk.Frame(frm)
    btn_row.grid(row=8, column=0, columnspan=2, sticky="ew", pady=6)
    btn_row.columnconfigure(0, weight=1)
    ttk.Button(btn_row, text="Compute", command=run_compute).grid(row=0, column=0, sticky="w")

    def open_author_site():
        webbrowser.open(AUTHOR_SITE_URL)

    ttk.Button(btn_row, text="Author's site", command=open_author_site).grid(
        row=0, column=1, sticky="e"
    )


    for w in (sp_a, sp_b, sp_k, sp_warn):
        w.bind("<Return>", lambda e: run_compute())
    root.mainloop()


if __name__ == "__main__":
    main()
