"""
GUI for Ramanujan telescopic cube decomposition experiments (logic in perl/cmd/clear_result.py).

Run from this folder:
  python decompose_gui_EN.py
"""

import sys
import traceback
import webbrowser
from pathlib import Path

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, scrolledtext, messagebox

_ROOT = Path(__file__).resolve().parent.parent
_CMD = _ROOT / "perl" / "cmd"
if str(_CMD) not in sys.path:
    sys.path.insert(0, str(_CMD))

from clear_result import (  # noqa: E402
    compute_ramanujan_decomposition,
    format_factorization,
    order_sides_for_display,
    wrap_equation_lines,
)

AUTHOR_SITE_URL = "https://nvvorobtsov.github.io/"


def en_cubes_phrase(n: int) -> str:
    """English count + 'cube' / 'cubes'."""
    n = abs(int(n))
    if n == 1:
        return "1 cube"
    return f"{n} cubes"


def _actual_text_widget(st: tk.Widget) -> tk.Text:
    """Resolve the inner Text widget for ScrolledText (layout differs by Python version)."""
    inner = getattr(st, "text", None)
    if isinstance(inner, tk.Text):
        return inner
    if isinstance(st, tk.Text):
        return st
    for ch in st.winfo_children():
        if isinstance(ch, tk.Text):
            return ch
    return st


def _estimate_wrap_chars(text_w: tk.Widget) -> int:
    """Approximate monospace characters that fit the widget width (for line wrapping)."""
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


# (a, b0, k, term count) — with b0=0 and these a,k, one cube on the left of "=", rest on the right
PRESET_EXAMPLES = [
    (50, 0, 4, 10),
    (50, 0, 49, 100),
    (50, 0, 499, 1000),
    (50, 0, 4999, 10000),
    (50, 0, 24999, 50000),
    (50, 0, 49999, 100000),
    (100, 0, 249999, 500000),
]

PRESET_HINTS_EN = [
    "~10 terms, left: 1 cube",
    "~100, left: 1 cube",
    "~1000, left: 1 cube",
    "~10000, left: 1 cube",
    "~50000, left: 1 cube",
    "~100000, left: 1 cube",
    "~500000, left: 1 cube (a=100)",
]


def build_output_parts(data: dict, *, wrap_width: int = 72):
    """Full output: header, wrapped identity lines, bottom separator line."""
    bar_w = min(max(wrap_width, 40), 200)
    sep = "=" * bar_w
    Ld, Rd = order_sides_for_display(data["L_final"], data["R_final"])
    header = [
        (
            f"Generating decomposition for a = {data['a']}, "
            f"b0 = {data['b_start']}, k = {data['k']}"
        ),
        f"Generated parameters. Sequence length will be: {data['total_terms']} terms.",
        "",
        "Result:",
        f"Left: {en_cubes_phrase(len(Ld))}",
        f"Right: {en_cubes_phrase(len(Rd))}",
        sep,
        f"{data['total_val']} = {data['factor_str']} =",
    ]
    eq_lines = wrap_equation_lines(Ld, Rd, wrap_width)
    return header, eq_lines, sep


def between_separators_one_line(data: dict, wrap_width: int) -> str:
    """Factorization line + identity between === lines, single string (no wraps)."""
    header, eq_lines, _ = build_output_parts(data, wrap_width=wrap_width)
    factor_line = header[-1]
    return factor_line.rstrip() + "".join(eq_lines)


def build_output(data: dict, term_count_only: bool, *, wrap_width: int = 72) -> str:
    if term_count_only:
        Ld, Rd = order_sides_for_display(data["L_final"], data["R_final"])
        return (
            f"a = {data['a']}, b0 = {data['b_start']}, k = {data['k']}\n"
            f"Terms in decomposition (after cancellations): {data['total_terms']}\n"
            f"Left: {en_cubes_phrase(len(Ld))}\n"
            f"Right: {en_cubes_phrase(len(Rd))}\n"
        )
    h, e, s = build_output_parts(data, wrap_width=wrap_width)
    return "\n".join(h + e + [s])


def insert_result_with_bold_left_side(tw: tk.Text, header: list, eq_lines: list, sep: str) -> None:
    """In identity lines, the left segment before the first ' = ' is bold and blue (#1565C0)."""
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

    left_zone = True
    for line in eq_lines:
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

    tw.insert(tk.END, sep + "\n")


def main():
    root = tk.Tk()
    root.title("Ramanujan decomposition — parameters a, b0, k")
    root.minsize(640, 880)

    frm = ttk.Frame(root, padding=12)
    frm.grid(row=0, column=0, sticky="nsew")
    root.rowconfigure(0, weight=1)
    root.columnconfigure(0, weight=1)
    frm.columnconfigure(1, weight=1)
    frm.rowconfigure(7, weight=1)

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

    ttk.Label(frm, text="b0 (initial b):").grid(row=1, column=0, sticky="w", pady=2)
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
        text="Term count only (no full expansion)",
        variable=only_count,
    )
    chk.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 4))

    ttk.Label(
        frm,
        text=(
            "Max. terms in decomposition — warn on large output\n"
            "(only when \"term count only\" is unchecked):"
        ),
        justify=tk.LEFT,
    ).grid(row=4, column=0, sticky="nw", pady=2)
    sp_warn = tk.Spinbox(
        frm,
        from_=4,
        to=2_000_000,
        increment=1,
        textvariable=var_warn_max,
        width=12,
    )
    sp_warn.grid(row=4, column=1, sticky="w", pady=2)

    ex_frame = ttk.LabelFrame(frm, text="Examples: (a, b0, k) → term count (reference)")
    ex_frame.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(10, 6))
    ex_frame.columnconfigure(0, weight=1)

    ttk.Label(ex_frame, text="Parameters a, b0, k").grid(row=0, column=0, sticky="w", padx=4, pady=2)
    ttk.Label(ex_frame, text="Terms").grid(row=0, column=1, sticky="w", padx=4, pady=2)
    ttk.Label(ex_frame, text="").grid(row=0, column=2, padx=2, pady=2)

    def make_apply(a_i, b_i, k_i):
        def _apply():
            var_a.set(a_i)
            var_b.set(b_i)
            var_k.set(k_i)

        return _apply

    for i, ((a_i, b_i, k_i, cnt), hint) in enumerate(
        zip(PRESET_EXAMPLES, PRESET_HINTS_EN), start=1
    ):
        param_txt = f"a = {a_i},  b0 = {b_i},  k = {k_i}"
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

    clip_block_state = {"data": None, "wrap": None}

    def copy_between_separators() -> None:
        d = clip_block_state["data"]
        w = clip_block_state["wrap"]
        if d is None or w is None:
            messagebox.showinfo(
                "No block",
                "Run a full computation first (do not use \"term count only\"), "
                "so text between the separator lines is available.",
            )
            return
        clipboard_set(between_separators_one_line(d, w))

    out_wrap = ttk.Frame(frm)
    out_wrap.grid(row=7, column=0, columnspan=2, sticky="nsew", pady=(4, 0))
    out_wrap.rowconfigure(1, weight=1)
    out_wrap.columnconfigure(0, weight=1)

    out_top = ttk.Frame(out_wrap)
    out_top.grid(row=0, column=0, sticky="ew")
    ttk.Label(out_top, text="Output").pack(side=tk.LEFT)

    out = scrolledtext.ScrolledText(
        out_wrap,
        height=28,
        width=88,
        font=("Consolas", 10),
        wrap=tk.NONE,
        exportselection=True,
    )

    tw = _actual_text_widget(out)

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
            messagebox.showerror("Parameters", "k must be >= 1")
            return
        if a == 0:
            messagebox.showerror("Parameters", "a must not be 0")
            return
        if warn_max < 1:
            messagebox.showerror("Parameters", "Warning threshold must be >= 1")
            return

        tw.delete("1.0", tk.END)
        tw.insert(tk.END, "Computing\n")
        tw.update_idletasks()

        use_styled = False
        text = ""
        header = eq_lines = sep_line = None
        clip_block_state["data"] = None
        clip_block_state["wrap"] = None

        try:
            data = compute_ramanujan_decomposition(a, b0, k, factorize=False)
            want_full = not only_count.get()

            if want_full and data["total_terms"] > warn_max:
                ok = messagebox.askyesno(
                    "Large output",
                    (
                        f"Terms in decomposition: {data['total_terms']}\n"
                        f"This exceeds the threshold ({warn_max}). Full output and "
                        f"factorization may take a long time.\n\n"
                        f"Continue?"
                    ),
                    icon="warning",
                )
                if not ok:
                    clip_block_state["data"] = None
                    clip_block_state["wrap"] = None
                    tw.delete("1.0", tk.END)
                    tw.insert(
                        tk.END,
                        f"Cancelled. Would have had {data['total_terms']} terms "
                        f"(warning threshold: {warn_max}).\n",
                    )
                    return

            if want_full:
                data = {
                    **data,
                    "factor_str": format_factorization(data["total_val"]),
                }

            wrap_w = _estimate_wrap_chars(out)
            if only_count.get():
                text = build_output(data, True, wrap_width=wrap_w)
            else:
                header, eq_lines, sep_line = build_output_parts(data, wrap_width=wrap_w)
                use_styled = True
        except Exception:
            use_styled = False
            text = traceback.format_exc()

        tw.delete("1.0", tk.END)
        if use_styled:
            insert_result_with_bold_left_side(tw, header, eq_lines, sep_line)
            clip_block_state["data"] = data
            clip_block_state["wrap"] = wrap_w
        else:
            tw.insert(tk.END, text)

    btn_row = ttk.Frame(frm)
    btn_row.grid(row=6, column=0, columnspan=2, sticky="ew", pady=6)
    btn_row.columnconfigure(0, weight=1)
    ttk.Button(btn_row, text="Compute", command=run_compute).grid(row=0, column=0, sticky="w")

    def open_author_site():
        webbrowser.open(AUTHOR_SITE_URL)

    ttk.Button(btn_row, text="Author's website", command=open_author_site).grid(
        row=0, column=1, sticky="e"
    )

    out.grid(row=1, column=0, sticky="nsew")

    for w in (sp_a, sp_b, sp_k, sp_warn):
        w.bind("<Return>", lambda e: run_compute())
    root.mainloop()


if __name__ == "__main__":
    main()
