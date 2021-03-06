import builtins
import more_itertools
import numpy as np


__all__ = ["get_datetime_at_mirror", "print"]


def get_datetime_at_mirror(fraw1_, i_mirror=0):
    Y, m, d, H, M, S, nanosecond = _get_sep_datetime_at_mirror(fraw1_, i_mirror)
    return np.datetime64(f"{Y}-{m:02}-{d:02}T{H:02}:{M:02}:{S:02}.{nanosecond:09}")


def _get_sep_datetime_at_mirror(fraw1_, i_mirror):
    Y = fraw1_["julian"] // 10000
    m = (fraw1_["julian"] // 100) % 100
    d = fraw1_["julian"] % 100

    _total_seconds = fraw1_["jsecond"]
    if i_mirror == 0 and fraw1_["num_mir"] == 0:
        nanosecond = 0
    elif 0 <= i_mirror < fraw1_["num_mir"]:
        _total_seconds += fraw1_["second"][..., i_mirror]
        nanosecond = (50 * fraw1_["clkcnt"][..., i_mirror] / 3 + fraw1_["jclkcnt"]).astype(int)
    else:
        raise IndexError(f"""Expected 0 <= i_mirror < {fraw1_["num_mir"]}, got {i_mirror}.""")

    if nanosecond > 999999999:
        nanosecond -= 1000000000
        _total_seconds += 1

    H = _total_seconds // 3600
    M = (_total_seconds // 60) % 60
    S = _total_seconds % 60

    return Y, m, d, H, M, S, nanosecond


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

    indices_mirror = np.arange(fraw1_["num_mir"])
    mirror_headers = [
        f" m  {m:>4} num_chan  {num_chan:>4}"
        for m, num_chan in zip(fraw1_["mir_num"][indices_mirror], fraw1_["num_chan"][indices_mirror])
    ]

    _, _, _, H, M, S, nanosecond = _get_sep_datetime_at_mirror(fraw1_, indices_mirror)
    mirror_times = [
        " event store start time -- {}:{:02}:{:02}.{:09d}".format(*args)
        for args in zip(H, M, S, nanosecond)
    ]

    signal_headers = [
        [
            f" hit {jp1:>3} chan(HI=00-FF, LO=100-11F, TR=200-21F)  {f'{chn_i_j:>02X}':>3} it0  {it0chn_i_j:>4} nt  {ntchn_i_j:>3}"
            for jp1, chn_i_j, it0chn_i_j, ntchn_i_j in zip(np.arange(num_chan_i) + 1, channel_i, it0_chan_i, nt_chan_i)
        ]
        for num_chan_i, channel_i, it0_chan_i, nt_chan_i in zip(
            fraw1_["num_chan"][indices_mirror], fraw1_["channel"][indices_mirror], fraw1_["it0_chan"][indices_mirror], fraw1_["nt_chan"][indices_mirror]
        )
    ]

    m_fadc_values = [
        [
            [mfdc_i_j_k for mfdc_i_j_k, k in zip(m_fadc_i_j, np.arange(nt_chan_i_j))]
            for m_fadc_i_j, nt_chan_i_j, _ in zip(m_fadc_i, nt_chan_i, np.arange(num_chan_i))
        ]
        for m_fadc_i, num_chan_i, nt_chan_i in zip(
            fraw1_["m_fadc"][indices_mirror].view("i1"), fraw1_["num_chan"][indices_mirror], fraw1_["nt_chan"][indices_mirror]
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
