try:
    from . import _dst_cffi as dst
except ImportError:
    import sys
    print(f"Run pydst/dst_extension_build.py first. (__file__={__file__})", file=sys.stderr)
    sys.exit(1)

from . import util

__all__ = ["util"]

