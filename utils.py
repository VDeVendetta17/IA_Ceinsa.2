import hashlib

def clean_rut(rut: str) -> str:
    return rut.replace(".", "").upper()

def rut_is_valid(rut: str) -> bool:
    try:
        rut = clean_rut(rut)
        num, dv = rut.split("-")
        reverse_digits = list(map(int, reversed(num)))
        factors = [2,3,4,5,6,7]
        s = 0
        for i, d in enumerate(reverse_digits):
            s += d * factors[i % len(factors)]
        mod = 11 - (s % 11)
        dv_calc = "0" if mod == 11 else "K" if mod == 10 else str(mod)
        return dv == dv_calc
    except Exception:
        return False

def mask_rut(rut: str) -> str:
    rut = clean_rut(rut)
    if "-" not in rut:
        return rut
    num, dv = rut.split("-")
    if len(num) <= 3:
        return f"***-{dv}"
    return f"{num[:-3] + '***'}-{dv}"

def safe_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
