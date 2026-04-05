import math
import sympy as sp
import argparse
from collections import Counter

def W(a, b):
    return a**7 - 3*a**4*b + a*(3*b**2 - 1)

def X(a, b):
    return a**7 - 3*a**4*(1 + b) + a*(2 + 6*b + 3*b**2)

def Y(a, b):
    return 2*a**6 - 3*a**3*(1 + 2*b) + 1 + 3*b + 3*b**2

def Z(a, b):
    return a**6 - 1 - 3*b - 3*b**2


def format_factorization(total_val):
    factors = sp.factorint(total_val)
    return "*".join([f"{p}^{e}" if e > 1 else f"{p}" for p, e in sorted(factors.items())])


def ru_cubes_phrase(n: int) -> str:
    """Число и слово «куб» в правильном числе (1 куб, 2 куба, 5 кубов)."""
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        w = "куб"
    elif n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        w = "куба"
    else:
        w = "кубов"
    return f"{n} {w}"


def order_sides_for_display(L_final, R_final):
    """Для вывода: слева — сторона с меньшим числом кубов (при строгом неравенстве меняем местами).

    Суммы кубов по обеим сторонам равны, тождество остаётся верным.
    """
    L, R = list(L_final), list(R_final)
    if len(L) > len(R):
        return R, L
    return L, R


def compute_ramanujan_decomposition(a, b_start, k, *, factorize=True):
    """Возвращает данные разложения без печати (для CLI и GUI).

    factorize=False пропускает sp.factorint (быстро для проверки числа членов в GUI).
    """
    # Collect all 4 polynomials for each step
    b_seq = list(range(b_start, b_start + k))

    w_seq = [W(a, b) for b in b_seq]
    x_seq = [X(a, b) for b in b_seq]
    y_seq = [Y(a, b) for b in b_seq]
    z_seq = [Z(a, b) for b in b_seq]

    # Base equation: W^3 - X^3 = Y^3 + Z^3
    # After telescopic cancellation of the left side, we get:
    # W_0^3 - X_{k-1}^3 = \sum (Y_i^3 + Z_i^3)

    left_raw = [w_seq[0], -x_seq[-1]]
    right_raw = []
    for y, z in zip(y_seq, z_seq):
        right_raw.extend([y, z])

    L_vals = []
    R_vals = []

    for val in left_raw:
        if val > 0:
            L_vals.append(val)
        elif val < 0:
            R_vals.append(abs(val))

    for val in right_raw:
        if val > 0:
            R_vals.append(val)
        elif val < 0:
            L_vals.append(abs(val))

    L_counts = Counter(L_vals)
    R_counts = Counter(R_vals)
    common = L_counts & R_counts

    L_final = list((L_counts - common).elements())
    R_final = list((R_counts - common).elements())

    L_final.sort()
    R_final.sort()

    total_terms = len(L_final) + len(R_final)
    total_val = sum(x**3 for x in L_final)
    factor_str = format_factorization(total_val) if factorize else None

    return {
        "a": a,
        "b_start": b_start,
        "k": k,
        "L_final": L_final,
        "R_final": R_final,
        "total_terms": total_terms,
        "total_val": total_val,
        "factor_str": factor_str,
    }


def try_defactored_equation_lines(L_final, R_final, width=72, *, lang="ru"):
    """Общий gcd оснований кубов по всем членам тождества (в порядке показа).

    Если gcd g > 1 — основания делятся на g; в сумме кубов общий множитель g³.
    Возвращает пятёрку:
      (1) строка про g³ (RU/EN по lang);
      (2) строка «N = факторизация(N) =» для сокращённой суммы N;
      (3) строки сокращённого тождества (wrap_equation_lines);
      (4) L2 — основания слева после деления на gcd (в порядке показа);
      (5) R2 — основания справа после деления на gcd.

    lang: \"ru\" | \"en\" — подписи к первой строке блока дефакторизации.

    Если gcd == 1 — ранний выход при первом же обнулении общей части (инкрементальный gcd).

    Возвращает None, если сокращать нечего или недостаточно оснований.
    """
    Ld, Rd = order_sides_for_display(L_final, R_final)
    bases = list(Ld) + list(Rd)
    if len(bases) < 2:
        return None
    g = abs(int(bases[0]))
    if g == 0:
        return None
    for b in bases[1:]:
        bi = abs(int(b))
        if bi == 0:
            return None
        g = math.gcd(g, bi)
        if g == 1:
            return None
    if g <= 1:
        return None
    L2 = [int(x) // g for x in Ld]
    R2 = [int(x) // g for x in Rd]
    v_left = sum(x**3 for x in L2)
    v_right = sum(x**3 for x in R2)
    if v_left != v_right:
        return None
    g3 = g**3
    if lang == "en":
        gcd_cube_line = f"Cubed gcd of bases (g³): {g3} = {format_factorization(g3)}"
    else:
        gcd_cube_line = f"Куб НОД оснований (g³): {g3} = {format_factorization(g3)}"
    factor_line = f"{v_left} = {format_factorization(v_left)} ="
    eq_lines = wrap_equation_lines(L2, R2, width)
    return (gcd_cube_line, factor_line, eq_lines, L2, R2)


def wrap_equation_lines(L_final, R_final, width=72):
    tokens = []
    for i, val in enumerate(L_final):
        tokens.append(f"{val}^3" if i == 0 else f"+{val}^3")
    tokens.append("=")
    for i, val in enumerate(R_final):
        tokens.append(f"{val}^3" if i == 0 else f"+{val}^3")

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


def generate_ramanujan_decomposition(a, b_start, k):
    data = compute_ramanujan_decomposition(a, b_start, k)
    L_final = data["L_final"]
    R_final = data["R_final"]
    total_terms = data["total_terms"]
    total_val = data["total_val"]
    factor_str = data["factor_str"]

    print(f"Разложение: a = {a}, b0 = {b_start}, k = {k}")
    print(f"Параметры сформированы. Число членов в последовательности: {total_terms}.\n")
    print("Результат:")
    L_disp, R_disp = order_sides_for_display(L_final, R_final)
    print(f"Слева: {ru_cubes_phrase(len(L_disp))}")
    print(f"Справа: {ru_cubes_phrase(len(R_disp))}")
    print("="*72)
    print(f"{total_val} = {factor_str} =")
    for line in wrap_equation_lines(L_disp, R_disp, 72):
        print(line)
    print("="*72)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Ramanujan cube decompositions.")
    parser.add_argument("--a", type=int, default=2, help="Parameter a (default: 2)")
    parser.add_argument("--b", type=int, default=10, help="Starting value for b (default: 10)")
    parser.add_argument("--k", type=int, default=5, help="Number of steps (default: 5)")

    args = parser.parse_args()
    generate_ramanujan_decomposition(args.a, args.b, args.k)
