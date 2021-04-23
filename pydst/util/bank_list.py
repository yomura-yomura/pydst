import numpy as np
from .. import _dst_cffi as dst
from typing import Iterable


__all__ = ["BankList"]


class BankList:
    element_type = np.dtype("i4")

    def __init__(self, size):
        self._bank_id = dst.lib.newBankList(size)

    def __del__(self):
        dst.lib.delBankList(self._bank_id)

    def __len__(self):
        return dst.lib.cntBankList(self._bank_id)

    def __iter__(self):
        return BankListIterator(self._bank_id)

    def __str__(self):
        return str(self.to_numpy())

    def __repr__(self):
        return f"BankList({self})"

    def to_numpy(self):
        return np.fromiter(self, dtype=self.element_type)

    def append(self, bank: int):
        dst.lib.addBankList(self._bank_id, bank)

    def extend(self, bank_list: Iterable[int]):
        for bank in bank_list:
            self.append(bank)

    def clear(self):
        dst.lib.clrBankList(self._bank_id)

    def set_all_banks(self):
        dst.lib.eventAllBanks(self._bank_id)


class BankListIterator:
    def __init__(self, bank_id):
        self._n = dst.ffi.new("int *")
        self._bank_id = bank_id

    def __del__(self):
        dst.ffi.release(self._n)

    def __iter__(self):
        return self

    def __next__(self):
        ret = dst.lib.itrBankList(self._bank_id, self._n)
        if ret == 0:
            raise StopIteration
        else:
            return ret