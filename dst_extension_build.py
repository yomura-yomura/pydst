from cffi import FFI
import pathlib
import pycparser
import pycparser.c_generator
import re
import numpy as np
import collections
import inspect
import subprocess
import os


def _get_invalids():
    invalid_func_names = []
    invalid_headers = []

    # 実体が定義されていないものを除外
    invalid_func_names += [
        # _で終わる名前なら定義されてる
        "astro_local",  # (inc/astro.h, src/uti/lib/astro.c)
        "dst_init_data",  # (inc/dst_data_proto.h, src/dst/lib/dst_data.c)

        # コメントアウトされてる (inc/astro.h, src/uti/lib/coords.c)
        "findTubes",

        # 全く無い (inc/mc04_detector.h)
        "mc04_detector_has_BR",
        "mc04_detector_has_BR_TAx4",
        "mc04_detector_has_LR",
        "mc04_detector_has_MD",
        "mc04_detector_has_MD_TAx4",
        "mc04_detector_has_TALE",
        "mc04_detector_has_TLS",
        "mc04_detector_is_hires",
        "mc04_detector_is_TA",
        "mc04_detector_is_mono",
        "mc04_detector_is_stereo",
        "mc04_detector_neye_active"
    ]

    # # stdio.hのインクルードができない限り除外
    # invalid_func_names += [
    #     "dsc_bank_list_",
    #     "dscBankList"
    # ]

    # zlib.hのインクルードができない限り除外
    invalid_headers += [
        "iomonitor.h"
    ]

    # ヘッダーで実体の宣言がされてしまってる"変な"ファイルを除外
    invalid_headers += [
        "geofd_tokuno_spotsize.h"
    ]

    return invalid_func_names, invalid_headers


_current_path = pathlib.Path(__file__).resolve().parent
fake_libc_path = _current_path / "fake_libc_include"

env_variable = "DST2KTA_PATH"

dst_standard_types_header = "dst_std_types.h"

parser = pycparser.CParser()

if env_variable not in os.environ:
    raise EnvironmentError(f"Environment variable '{env_variable}' is not defined.")
else:
    dst2k_path = pathlib.Path(os.environ[env_variable])

if not dst2k_path.exists():
    raise FileNotFoundError(dst2k_path)

include_dir_path = dst2k_path / "inc"
if not include_dir_path.exists():
    raise FileNotFoundError(include_dir_path)

lib_dir_path = dst2k_path / "lib"
if not lib_dir_path.exists():
    raise FileNotFoundError(lib_dir_path)

src_bank_path = dst2k_path / "src" / "bank" / "lib"
if not src_bank_path.exists():
    raise FileNotFoundError(src_bank_path)

implied_includes = ["stdlib.h", dst_standard_types_header]

invalid_func_names, invalid_headers = _get_invalids()

total_header = sum(1 for h in (p.name for p in include_dir_path.glob("*.h")) if h not in invalid_headers)


def get_n_recursively_called(skip=0):
    stack = inspect.stack()
    frame = stack[1 + skip][0]
    return sum(1 for parent_frame, *_ in stack[2 + skip:] if parent_frame.f_code == frame.f_code)


def preprocess_file(path):
    return subprocess.run(["gcc", "-E", str(path)], stdout=subprocess.PIPE).stdout.decode("ascii")


def preprocess_text(text: str, opts=[]):
    p = subprocess.Popen(["gcc", "-E", *opts, "-"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate(text.encode())
    if err != b"":
        raise IOError(err.decode())
    return out.decode()


def get_txt_std_header(name):
    return pycparser.preprocess_file(fake_libc_path / name)


def get_txt(h, separate_includes=False):
    if (include_dir_path / h).exists():
        txt = "".join(line for line in open(include_dir_path / h))

        includes = implied_includes.copy()
        if h in includes:
            includes.pop(includes.index(h))

        if separate_includes:
            return txt, includes
        else:
            return "\n".join((*(f'#include "{h}"' for h in includes), txt))
    elif (fake_libc_path / h).exists():
        txt = "".join(l for l in open(fake_libc_path / h))
        if separate_includes:
            return txt, []
        else:
            return txt
    else:
        raise FileNotFoundError(h)


def get_all_header_dependencies(h, return_flatten=False):
    txt = get_txt(h)

    other_headers = [
        h
        for h in collections.Counter([
            os.path.basename(m[1])
            for m in re.finditer(r'^#include ["<](.+)[">].*\n', txt, re.MULTILINE)
        ]).keys()
    ]

    if h in other_headers:  # TODO: なぜか、自分自身が含まれることがある。原因を知らべる。
        other_headers.pop(other_headers.index(h))

    all_headers = [h, *other_headers]

    # インクルード漏れのヘッダーファイルの修正
    table = [
        (
            ["jmdtubeprofile_dst.h", "jbrtubeprofile_dst.h", "jlrtubeprofile_dst.h"],
            "jfdtubeprofile_dst.h"
        ),
        (
            ["hctim_dst.h", "fpho1_dst.h", "brpho_dst.h", "lrpho_dst.h",
             "hbar_dst.h", "hped1_dst.h", "hmc1_dst.h", "hraw1_dst.h",
             "hpkt1_dst.h", "hcal1_dst.h", "hnpe_dst.h", "hrxf1_dst.h",
             "fscn1_dst.h"],
            "univ_dst.h"
        ),
        (
            ["ontime2_dst.h"],
            "hsum_dst.h"
        )
    ]

    for hs, should_be_included in table:
        if np.isin(all_headers, hs).any():
            other_headers.append(should_be_included)

    if return_flatten:
        if len(other_headers) > 0:
            return tuple(collections.Counter((
                *other_headers,
                *(
                    ooh
                    for oh in other_headers
                    for ooh in get_all_header_dependencies(oh, return_flatten=True)
                )
            )).keys())
        else:
            return []
    else:
        if len(other_headers) > 0:
            return {
                oh: get_all_header_dependencies(oh, return_flatten=False)
                for oh in other_headers
            }
        else:
            return None


def parse_header(h, ext={}, debug=False, remove_dependencies=True, show=False):
    def print_debug(*s, **kwargs):
        print(f"[DEBUG] {'    ' * get_n_recursively_called(1)}", *s, **kwargs)

    if debug:
        print_debug(h)

    if h in ext:
        if debug:
            print_debug(f"{h} already in ext")
        return None

    txt, includes = get_txt(h, separate_includes=True)

    other_headers = get_all_header_dependencies(h, return_flatten=True)
    includes.extend(reversed(other_headers))

    txt = "\n".join((*(f'#include "{h}"' for h in includes), txt))

    if debug:
        print_debug(h, other_headers)

    txt = preprocess_text(txt, [f"-I{fake_libc_path}", f"-I{include_dir_path}"])

    ast = parser.parse(txt, include_dir_path / h)

    if remove_dependencies:
        skip_length = 0
        if len(other_headers) > 0:
            if remove_dependencies:
                skip_length = sum(
                    len(parse_header(oh, ext, debug, remove_dependencies=True)) if oh not in ext else len(ext[oh])
                    for oh in other_headers
                )
            else:
                skip_length = sum(
                    len(parse_header(oh, ext, debug, remove_dependencies=False)) if oh not in ext else len(ext[oh])
                    for oh in other_headers
                )

        if debug:
            print_debug(f"{h}, {skip_length = }")
        ext[h] = ast.ext[skip_length:]
    else:
        ext[h] = ast.ext

    print(f"read headers {len(ext):>3} / {total_header}\r", end="")

    # if show:
    #     print(g.visit(pycparser.c_ast.FileAST(ext[h])))
    return ext[h]


def build():
    print(f"* Received Environment Variable '{env_variable}' as {dst2k_path}")

    # if not build_path.exists():
    #     raise RuntimeWarning(f"do not run {__file__} directly at first.")

    bank_header_names = [
        h for h in (c.with_suffix(".h").name for c in src_bank_path.glob("*.c")) if h not in invalid_headers
    ]

    other_header_names = [
        h.name for h in include_dir_path.glob("*.h")
        if (h.name not in bank_header_names) and (h.name not in invalid_headers)
    ]
    other_header_names.insert(0, other_header_names.pop(other_header_names.index(dst_standard_types_header)))

    all_ext = {}
    for h in (p.name for p in include_dir_path.glob("*.h")):
        if h not in invalid_headers:
            parse_header(h, all_ext)

    bank_ext = {k: all_ext[k] for k in (h for h in all_ext.keys() if h in bank_header_names)}
    other_ext = {k: all_ext[k] for k in other_header_names if k not in bank_header_names}

    # ext to cdef

    g = pycparser.c_generator.CGenerator()

    std_types_cdefs = g.visit(pycparser.c_ast.FileAST([
        e
        for h in collections.Counter(
            implied_includes +
            [h for ih in implied_includes for h in get_all_header_dependencies(ih)]
        ).keys()
        for e in all_ext[h]
        # FILE struct is supported in cffi library
        if not (isinstance(e.type, pycparser.c_ast.TypeDecl) and e.name == "FILE")
    ]))

    bank_cdefs = g.visit(pycparser.c_ast.FileAST([
        e for ext in bank_ext.values() for e in ext
        # 実体が定義されていないものを除外
        if not (isinstance(e.type, pycparser.c_ast.FuncDecl) and e.name in [
            # 全く無い (inc/atmpar_dst.h)
            "atmpar_h2mo", "atmpar_h2mo_deriv", "atmpar_mo2h",
            # 全く無い (inc/hpkt1_dst.h)
            "hpkt1_common_to_hraw1_",
            # 全く無い (inc/tadaq_dst.h)
            "tadaq_time_fprint", "tadaq_time_print_",
            # 全く無い (inc/tasdmonitor_dst.h)
            "tasdmonitor_dst_to_common_",
            # 全く無い (inc/tlmsnp_dst.h)
            "tlmsnp_time_fprint", "tlmsnp_time_print_",

            # _で終わる名前なら定義されてる (inc/fraw1_dst.h, src/bank/lib/fraw1_dst.c),
            "fraw1_time_fprint",
        ])
    ]))

    other_cdefs = g.visit(pycparser.c_ast.FileAST([
        e for ext in other_ext.values() for e in ext
        # extern宣言されてるけど、実体無い
        if not (e.storage == ["extern"] and isinstance(e.type, pycparser.c_ast.TypeDecl) and e.name in ["geoh_", "geohr2_"])
        if not (isinstance(e.type, pycparser.c_ast.FuncDecl) and e.name in invalid_func_names)
    ]))

    dst_includes = "\n".join(f'#include "{include_dir_path / f}"' for f in other_header_names)

    ffi_builder = FFI()
    ffi_builder.cdef(std_types_cdefs)
    ffi_builder.cdef(other_cdefs, override=True)  # TODO: should be override=False
    # ffi_builder.cdef(other_cdefs)
    ffi_builder.cdef(bank_cdefs)

    target_fn = "_dst_cffi"

    ffi_builder.set_source(
        target_fn, dst_includes,
        include_dirs=[str(include_dir_path)],
        library_dirs=[str(lib_dir_path)],
        libraries=['dst2k', "bz2", "m", "c", "z"]
    )

    ffi_builder.compile(verbose=True)
    p = pathlib.Path(target_fn)
    p.with_suffix(".o").unlink()
    p.with_suffix(".c").unlink()

    build_path = _current_path/"build"
    if build_path.exists():
        lib_paths = list(pathlib.Path(_current_path).glob(f"{target_fn}.*"))
        assert len(lib_paths) == 1
        lib_path = lib_paths[0]
        lib_path.rename(build_path/"lib"/"pydst"/lib_path.name)
    else:
        raise FileNotFoundError(build_path)

if __name__ == "__main__":
    build()
