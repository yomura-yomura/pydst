import io
import os
import pathlib
import gzip
import shutil
import sys

import numpy as np
from .. import _dst_cffi as dst
from .. import c_to_py
from . import bank_list
import builtins
import tqdm
import numpy_utility as npu


def open(file, mode="r"):
    """
    The available modes are:
    ========= ===============================================================
    Character Meaning
    --------- ---------------------------------------------------------------
    'r'       open for reading (default)
    'w'       open for writing, truncating the file first
    'a'       open for writing, appending to the end of the file if it exists
    ========= ===============================================================
    """

    path = pathlib.Path(file)
    if mode not in DSTIOWrapper.mode_table:
        raise ValueError(f"invalid mode: '{mode}'")

    return DSTIOWrapper(path, mode)


from contextlib import contextmanager


@contextmanager
def stdout_redirected(to=os.devnull):
    """
    import os

    with stdout_redirected(to=filename):
        print("from Python")
        os.system("echo non-Python applications are also supported")
    """
    fd = sys.stdout.fileno()

    ##### assert that Python and C stdio write using the same file descriptor
    ####assert libc.fileno(ctypes.c_void_p.in_dll(libc, "stdout")) == fd == 1

    def _redirect_stdout(to):
        sys.stdout.close()  # + implicit flush()
        os.dup2(to.fileno(), fd)  # fd writes to 'to' file
        sys.stdout = os.fdopen(fd, 'w')  # Python writes to fd

    with os.fdopen(os.dup(fd), 'w') as old_stdout:
        with open(to, 'w') as file:
            _redirect_stdout(to=file)
        try:
            yield  # allow code to be run with the redirected stdout
        finally:
            _redirect_stdout(to=old_stdout)


class DSTIOWrapper:
    used_unit_numbers = {0}
    mode_table = {
        "r": 1,
        "w": 2,
        "a": 3
    }

    def __init__(self, name: os.PathLike, mode: str):
        path = pathlib.Path(name)

        if mode not in DSTIOWrapper.mode_table:
            raise ValueError(f"invalid mode: '{mode}'")

        if mode == "r" and not path.exists():
            raise FileNotFoundError(f"[Errno 2] No such file: '{path}'")

        # self.in_unit = next(i for i in itertools.count() if i not in self.running_unit_numbers)
        self.in_unit = max(DSTIOWrapper.used_unit_numbers) + 1
        self.name = name
        self.mode = mode
        self.closed = False
        self.is_gz_file = path.suffix == ".gz"

        in_mode = DSTIOWrapper.mode_table[mode]

        if self.is_gz_file:
            if mode in ("w", "a"):
                self._uncompressed_path = path.with_suffix("")
                builtins.open(path, f"{mode}b").close()
            else:
                self._uncompressed_path = pathlib.Path("/tmp") / path.with_suffix("").name

            if mode in ("r", "a"):
                if not self._uncompressed_path.exists():
                    with gzip.open(path, "rb") as f_uncompressed:
                        with builtins.open(self._uncompressed_path, "wb") as f:
                            shutil.copyfileobj(f_uncompressed, f)

            path = self._uncompressed_path

        dst.lib.dstOpenUnit(self.in_unit, str(path).encode('ascii'), in_mode)
        DSTIOWrapper.used_unit_numbers.add(self.in_unit)

        self.event = dst.ffi.new('int32_t *')

    def __str__(self):
        return f"<{self.__class__.__name__} name='{self.name}' mode='{self.mode}' in_unit={self.in_unit}>"

    def __repr__(self):
        return self.__str__()

    def __del__(self):
        dst.ffi.release(self.event)
        if not self.closed:
            self.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        dst.lib.dstCloseUnit(self.in_unit)
        DSTIOWrapper.used_unit_numbers.remove(self.in_unit)
        self.closed = True

        if self.is_gz_file:
            if self.mode in ("w", "a"):
                with gzip.open(self.name, f"{self.mode}b") as f_compressed:
                    with builtins.open(self._uncompressed_path, "rb") as f:
                        shutil.copyfileobj(f, f_compressed)

            if self._uncompressed_path.exists():
                self._uncompressed_path.unlink()

    def read_dst(self, want_bank_names=None, return_as_numpy_array=True):
        if self.mode != "r":
            raise io.UnsupportedOperation("not readable")

        want_bank = bank_list.BankList(150)
        if want_bank_names is None:
            want_bank.set_all_banks()
        else:
            want_bank.extend(get_id_from_name(want_bank_names))
        got_bank = bank_list.BankList(150)

        # null_fds = [os.open(os.devnull, os.O_RDWR) for _ in range(2)]
        # # save the current file descriptors to a tuple
        # save = os.dup(1), os.dup(2)

        # ret = []
        while True:
            # # put /dev/null fds on 1 and 2
            # os.dup2(null_fds[0], 1)
            # os.dup2(null_fds[1], 2)

            rc = dst.lib.eventRead(self.in_unit, want_bank._bank_id, got_bank._bank_id, self.event)

            # # restore file descriptors so I can print the results
            # os.dup2(save[0], 1)
            # os.dup2(save[1], 2)

            if self.event[0] == 0:
                break
                # raise StopIteration
            if rc <= 0:
                raise ValueError(rc)

            bank_names = get_name_from_id(list(got_bank))
            row = {bn: c_to_py.convert(getattr(dst.lib, f"{bn}_")) for bn in bank_names}
            # if return_as_numpy_array:
            #     ret.append(npu.from_dict(row))
            # else:
            #     ret.append(row)
            if return_as_numpy_array:
                yield npu.from_dict(row)[0]
            else:
                yield row

        # # # close the temporary fds
        # # os.close(null_fds[0])
        # # os.close(null_fds[1])
        #
        # if return_as_numpy_array:
        #     return np.concatenate(ret)
        # else:
        #     return ret

    def write_dst(self, event_list: list, show_progress=True):
        if self.mode == "r":
            raise io.UnsupportedOperation("not writable")

        got_bank = bank_list.BankList(150)

        if show_progress:
            event_list = tqdm.tqdm(event_list, file=sys.stdout)

        for event in event_list:
            names = tuple(event.keys())

            got_bank.clear()
            got_bank.extend(get_id_from_name(names))

            for name in names:
                var = getattr(dst.lib, f"{name}_")
                for k, v in event[name].items():
                    obj = getattr(var, k)
                    if isinstance(obj, dst.ffi.CData):
                        cname = dst.ffi.typeof(obj).cname
                        setattr(var, k, dst.ffi.from_buffer(cname, v))
                    else:
                        setattr(var, k, v)

            dst.lib.eventWrite(self.in_unit, got_bank._bank_id, 1)

    def dump(self):
        pass


def get_id_from_name(bank_name):
    @np.vectorize
    def _inner(bnm):
        return dst.lib.eventIdFromName(dst.ffi.from_buffer(bnm))

    return _inner(np.asarray(bank_name, "S"))


def get_name_from_id(bank_id):
    size = 32
    text = dst.ffi.new(f'char[{size}]')

    @np.vectorize
    def _inner(bid):
        dst.lib.eventNameFromId(bid, text, size)
        return dst.ffi.string(text).decode()

    ret = _inner(bank_id)
    dst.ffi.release(text)
    return ret
