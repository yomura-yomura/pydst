try:
    from . import _dst_cffi as dst
except ImportError:
    import sys
    print("Run pydst/dst_extension_build.py first.", file=sys.stderr)
    sys.exit(1)

from . import util

__all__ = ["util"]

