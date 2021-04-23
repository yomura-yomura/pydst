import pydst


# path = "/Users/yomura/niche/hybrid_analysis/java/dst/niche-tale.hybrid_00.dst.gz"
# path = "/Users/yomura/niche/hybrid_analysis/fd_data/pass0/20190401/y2019m04d01p012.dataNOCUTS.tale.fraw1.dst.gz"
path = "/Users/yomura/niche/hybrid_analysis/fd_data/pass0/data/20190401/y2019m04d01p001.dataNOCUTS.tale.fraw1.dst.gz"
# data = load_dst(path)

with pydst.util.event.open(path) as fr:
    data = fr.read_dst()
    data1 = data
    with pydst.util.event.open("copied.dst.gz", "w") as fw:
        fw.write_dst(data1)


# with pydst.util.event.open(path) as f:
#     data1 = f.read_dst()

with pydst.util.event.open("copied.dst.gz") as f:
    data2 = f.read_dst()

# with pydst.util.event.open("/Users/yomura/niche/hybrid_analysis/fd_data/pass0/data/20190401/y2019m04d01p002.dataNOCUTS.tale.fraw1.dst.gz") as f:
#     data2 = f.read_dst()

import tqdm
import numpy as np
