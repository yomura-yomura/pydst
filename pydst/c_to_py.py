import numpy as np
from . import _dst_cffi as dst
import re


_c_data_types = {
    "bool": "?",
    "int": "i",
    "short": "i",
    "char": "S",
    "wchar_t": "U", "char16_t": "U", "char32_t": "U",
    "float": "f", "double": "f",
    "long double": "f",
}

table = {
    k: np.dtype(f"{kind}{dst.ffi.alignof(k)}" if kind in ("i", "S", "U", "f") else kind)
    for k, kind in _c_data_types.items()
}


def convert(bank):
    return {attr: convert_to_pyobject(getattr(bank, attr)) for attr in dir(bank)}


def convert_to_pyobject(obj):
    if isinstance(obj, dst.ffi.CData):
        type_ = dst.ffi.typeof(obj)
        if type_.kind == "primitive":
            return np.array(obj, dtype=table[type_.cname])
        elif type_.kind == "array":
            shape = tuple(int(m[1]) for m in re.finditer(r"\[(\d+)\]", type_.cname))
            return np.frombuffer(dst.ffi.buffer(obj), dtype=table[type_.cname.split("[")[0]]).copy().reshape(shape)
        else:
            raise NotImplementedError(type_.kind)
    else:
        return obj

