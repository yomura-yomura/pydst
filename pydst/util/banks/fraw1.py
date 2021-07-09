import builtins
import more_itertools
import numpy as np


def get_datetime_at_mirror(fraw1_, i_mirror=0):
    Y = fraw1_["julian"] // 10000
    m = (fraw1_["julian"] // 100) % 100
    d = fraw1_["julian"] % 100
    _total_seconds = fraw1_["jsecond"] + fraw1_["second"][i_mirror]
    H = _total_seconds // 3600
    M = (_total_seconds // 60) % 60
    S = _total_seconds % 60
    nanosecond = (50 * fraw1_["clkcnt"][i_mirror] / 3 + fraw1_["jclkcnt"]).astype(int)
    return np.datetime64(f"{Y}-{m:02}-{d:02}T{H:02}:{M:02}:{S:02}.{nanosecond:09}")


def print(fraw1_):
    header = "\n".join([
        " evt_code {event_code:>4} run start: {Y}/{m}/{d} {H}:{M:02}:{S:02}.{nanosecond:09d}".format(
            event_code=fraw1_["event_code"],
            m=(fraw1_["julian"] // 100) % 100, d=fraw1_["julian"] % 100, Y=fraw1_["julian"] // 10000,
            H=fraw1_["jsecond"] // 3600, M=(fraw1_["jsecond"] // 60) % 60, S=fraw1_["jsecond"] % 60,
            nanosecond=fraw1_["jclkcnt"]
        ),
        " site  {site:>4} part  {part:>4} event_num  {event_num:>4} num_mir  {num_mir:>4}".format(
            site=fraw1_["site"],
            part=fraw1_["part"],
            event_num=fraw1_["event_num"],
            num_mir=fraw1_["num_mir"],
        )
    ])

    i = np.arange(fraw1_["num_mir"])
    mirror_headers = [
        f" m  {m:>4} num_chan  {num_chan:>4}"
        for m, num_chan in zip(fraw1_["mir_num"][i], fraw1_["num_chan"][i])
    ]

    mirror_times = [
        " event store start time -- {H}:{M:02}:{S:02}.{nanosecond:09d}".format(
            H=ss // 3600,
            M=(ss // 60) % 60,
            S=ss % 60,
            nanosecond=cc
        )
        for ss, cc in zip(
            fraw1_["jsecond"] + fraw1_["second"][i],
            (50 * fraw1_["clkcnt"][i] / 3 + fraw1_["jclkcnt"]).astype(int)
        )
    ]

    signal_headers = [
        [
            f" hit {jp1:>3} chan(HI=00-FF, LO=100-11F, TR=200-21F)  {f'{chn_i_j:>02X}':>3} it0  {it0chn_i_j:>4} nt  {ntchn_i_j:>3}"
            for jp1, chn_i_j, it0chn_i_j, ntchn_i_j in zip(np.arange(num_chan_i) + 1, channel_i, it0_chan_i, nt_chan_i)
        ]
        for num_chan_i, channel_i, it0_chan_i, nt_chan_i in zip(
            fraw1_["num_chan"][i], fraw1_["channel"][i], fraw1_["it0_chan"][i], fraw1_["nt_chan"][i]
        )
    ]

    m_fadc_values = [
        [
            [mfdc_i_j_k for mfdc_i_j_k, k in zip(m_fadc_i_j, np.arange(nt_chan_i_j))]
            for m_fadc_i_j, nt_chan_i_j, _ in zip(m_fadc_i, nt_chan_i, np.arange(num_chan_i))
        ]
        for m_fadc_i, num_chan_i, nt_chan_i in zip(
            fraw1_["m_fadc"][i].view("i1"), fraw1_["num_chan"][i], fraw1_["nt_chan"][i]
        )
    ]

    signals = [
        [
            "\n".join(
                "".join(col for col in row)
                for row in more_itertools.windowed((f" {e:02X}" for e in m_fadc_i_j), n=20, step=20)
            )
            for m_fadc_i_j in m_fadc_i
        ]
        for m_fadc_i in m_fadc_values
    ]

    builtins.print(header)
    builtins.print(
       "\n".join(
           more_itertools.roundrobin(
                mirror_headers,
                mirror_times,
                (
                    "\n".join(more_itertools.roundrobin(signal_headers_i, signals_i))
                    for signal_headers_i, signals_i in zip(signal_headers, signals)
                )
            )
       )
    )
