"""
GUI для экспериментов с телескопическим разложением.
Файл clear_result.py должен лежать в той же папке (скачайте оба с сайта публикации 5).

Запуск:
  python decompose_gui.py
"""

import sys
import traceback
from typing import Optional, Tuple
import webbrowser
from pathlib import Path

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, scrolledtext, messagebox

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


def between_separators_one_line(
    data: dict,
    wrap_width: int,
    defactor_bundle: Optional[Tuple[str, str, list]] = None,
    omit_raw_decomposition: bool = False,
) -> str:
    """Текст между линиями === без переносов (как одна строка) для копирования."""
    if omit_raw_decomposition and defactor_bundle:
        d_g3, d_n, d_eq = defactor_bundle
        return (
            DEFACTOR_SECTION_TITLE
            + "\n"
            + d_g3
            + "\n"
            + d_n
            + "\n"
            + "\n".join(d_eq)
        )
    header, eq_lines, _ = build_output_parts(data, wrap_width=wrap_width)
    factor_line = header[-1]
    s = factor_line.rstrip() + "".join(eq_lines)
    if defactor_bundle:
        d_g3, d_n, d_eq = defactor_bundle
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
    return s


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
    defactor_bundle: Optional[Tuple[str, str, list]] = None,
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
        d_g3, d_n, d_eq = defactor_bundle
        if eq_lines:
            tw.insert(tk.END, "\n")
        tw.insert(tk.END, DEFACTOR_SECTION_TITLE + "\n")
        tw.insert(tk.END, d_g3 + "\n")
        tw.insert(tk.END, d_n + "\n")
        _insert_eq_lines_bold_left(tw, d_eq, tag)

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
    frm.rowconfigure(8, weight=1)

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

    ttk.Label(
        frm,
        text=(
            "Макс. членов разложения — предупреждать о большом выводе\n"
            "(только если галочка «только число» выключена):"
        ),
        justify=tk.LEFT,
    ).grid(row=5, column=0, sticky="nw", pady=2)
    sp_warn = tk.Spinbox(
        frm,
        from_=4,
        to=2_000_000,
        increment=1,
        textvariable=var_warn_max,
        width=12,
    )
    sp_warn.grid(row=5, column=1, sticky="w", pady=2)

    ex_frame = ttk.LabelFrame(frm, text="Примеры: тройка параметров → число членов (для ориентира)")
    ex_frame.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(10, 6))
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
            )
        )

    out_wrap = ttk.Frame(frm)
    out_wrap.grid(row=8, column=0, columnspan=2, sticky="nsew", pady=(4, 0))
    out_wrap.rowconfigure(1, weight=1)
    out_wrap.columnconfigure(0, weight=1)

    out_top = ttk.Frame(out_wrap)
    out_top.grid(row=0, column=0, sticky="ew")
    ttk.Label(out_top, text="Результат").pack(side=tk.LEFT)

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

    def run_compute():
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
        clip_block_state["data"] = None
        clip_block_state["wrap"] = None
        clip_block_state["defactor_bundle"] = None
        clip_block_state["omit_raw_decomposition"] = False

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

            wrap_w = _estimate_wrap_chars(out)
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
                use_styled = True
        except Exception:
            use_styled = False
            text = traceback.format_exc()

        tw.delete("1.0", tk.END)
        if use_styled:
            insert_result_with_bold_left_side(
                tw, header, eq_lines, sep_line, defactor_bundle
            )
            clip_block_state["data"] = data
            clip_block_state["wrap"] = wrap_w
            clip_block_state["defactor_bundle"] = defactor_bundle
            clip_block_state["omit_raw_decomposition"] = bool(
                var_defactor.get() and defactor_bundle is not None
            )
        else:
            tw.insert(tk.END, text)

    btn_row = ttk.Frame(frm)
    btn_row.grid(row=7, column=0, columnspan=2, sticky="ew", pady=6)
    btn_row.columnconfigure(0, weight=1)
    ttk.Button(btn_row, text="Вычислить", command=run_compute).grid(row=0, column=0, sticky="w")

    def open_author_site():
        webbrowser.open(AUTHOR_SITE_URL)

    ttk.Button(btn_row, text="Сайт автора", command=open_author_site).grid(
        row=0, column=1, sticky="e"
    )

    out.grid(row=1, column=0, sticky="nsew")

    for w in (sp_a, sp_b, sp_k, sp_warn):
        w.bind("<Return>", lambda e: run_compute())
    root.mainloop()


if __name__ == "__main__":
    main()
