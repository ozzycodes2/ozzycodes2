"""PNG frames to a transparent, two-entry, forever-looping GIF.

Every constant here was measured against the players that will show it, not
chosen:

- Frame delays of 0 and 1 centisecond are clamped *up* to 100ms by both
  Chromium and Firefox, so 2cs is the honoured floor and only 1, 2, 4, 5, 10,
  20, 25, 50 and 100 fps come out exact.
- Dither cost over 24 frames: none 54,944 B, atkinson 56,037, floyd_steinberg
  61,981, bayer 68,510. `atkinson` is the right default for flat vector art and
  needs ffmpeg 6.0.
- A generous palette is expensive: re-encoding a two-colour reference GIF with
  `max_colors=32` grew it from 117 KB to 291 KB.
"""
import re
import shutil
import struct
import subprocess

# ffmpeg rejects `max_colors=2` alongside `reserve_transparent=1`, and reserving
# the slot costs two entries rather than one, so 3 is both the floor and what
# yields a single painted colour.
MIN_COLOURS = 3
MIN_DELAY_CS = 2
MIN_FFMPEG = (6, 0)

_VERSION = re.compile(r"ffmpeg version \D*(\d+)\.(\d+)")


def parse_version(banner):
    """`(major, minor)` from ffmpeg's first line, or `None` if it has none.

    A git-snapshot build reports a date where the version goes, which is not a
    version this can compare against the floor.
    """
    m = _VERSION.match(banner.strip())
    return (int(m[1]), int(m[2])) if m else None


def ffmpeg_version():
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is not installed; see tools/brains/README.md")
    out = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, check=True)
    found = parse_version(out.stdout.splitlines()[0])
    if found is None:
        raise RuntimeError(f"cannot read an ffmpeg version from {out.stdout.splitlines()[0]!r}")
    return found


def chain(colours):
    """The filter graph, named so the dither and the reserved slot are checkable.

    Neither survives into the output bytes: the palette says nothing about how
    it was applied, and a cheaper dither only shows up as a bigger file.
    """
    return (
        "[0:v]split[a][b];"
        f"[a]palettegen=max_colors={colours}:reserve_transparent=1:stats_mode=diff[p];"
        "[b][p]paletteuse=dither=atkinson:diff_mode=rectangle:alpha_threshold=128"
    )


def gif(frames, out, *, delay_cs, colours=MIN_COLOURS, version=None):
    """Encode `frames` — PNG bytes, in order — to `out`.

    `colours` is the palette cap passed to `palettegen`; at the default of 3 one
    slot goes to transparency and the drawing keeps a single painted colour.
    `version` exists so the floor check is testable without a second ffmpeg on
    the machine.
    """
    if not frames:
        raise ValueError("no frames to encode")
    if delay_cs < MIN_DELAY_CS:
        raise ValueError(
            f"delay {delay_cs}cs is below the {MIN_DELAY_CS}cs floor: "
            "browsers clamp 0 and 1 up to 100ms"
        )
    if colours < MIN_COLOURS:
        raise ValueError(f"colours must be at least {MIN_COLOURS} to reserve a transparent entry")

    found = version or ffmpeg_version()
    if found < MIN_FFMPEG:
        raise RuntimeError(
            f"ffmpeg {found[0]}.{found[1]} has no atkinson dither; "
            f"{MIN_FFMPEG[0]}.{MIN_FFMPEG[1]} or newer is required"
        )

    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "image2pipe", "-c:v", "png", "-framerate", f"{100 // delay_cs}",
         "-i", "-", "-filter_complex", chain(colours), "-loop", "0", str(out)],
        input=b"".join(frames),
        check=True,
    )


def _header(path):
    raw = path.read_bytes()
    if not raw.startswith(b"GIF8"):
        raise ValueError(f"{path} is not a GIF")
    return raw


def size(path):
    raw = _header(path)
    return struct.unpack("<HH", raw[6:10])


def palette(path):
    """`(table, transparent_index)` straight out of the file's own bytes.

    Read from the header rather than through a decoder so the check does not
    depend on a library agreeing with the encoder about what it wrote. ffmpeg
    always emits 256 entries and pads the unused ones, so the painted colours
    are the distinct entries, not the table's length. `transparent_index` is
    `None` when the control block does not set the flag — an opaque pin, which
    is a slab on one of GitHub's two themes.
    """
    raw = _header(path)
    if not raw[10] & 0x80:
        raise ValueError(f"{path} has no global colour table")
    count = 2 ** ((raw[10] & 0x07) + 1)
    table = [tuple(raw[13 + 3 * i : 16 + 3 * i]) for i in range(count)]

    at = raw.find(b"\x21\xf9\x04", 13 + 3 * count)
    if at < 0 or not raw[at + 3] & 1:
        return table, None
    return table, raw[at + 6]


def loops(path):
    """Loop count from the Netscape extension; 0 means forever.

    The `NETSCAPE2.0` marker is written whatever the count is, so its presence
    proves nothing — a count of 1 plays once and parks on the last frame.
    """
    raw = _header(path)
    at = raw.find(b"NETSCAPE2.0")
    if at < 0:
        raise ValueError(f"{path} declares no loop count")
    # …"NETSCAPE2.0", sub-block size 0x03, index 0x01, then the count.
    return struct.unpack("<H", raw[at + 13 : at + 15])[0]


def delay(path):
    """Frame delay in centiseconds, off the first graphic control extension."""
    raw = _header(path)
    at = raw.find(b"\x21\xf9\x04")
    if at < 0:
        raise ValueError(f"{path} declares no frame delay")
    return struct.unpack("<H", raw[at + 4 : at + 6])[0]
