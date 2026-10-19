"""Tests for GIF encoding.

The numbers here are measured, not chosen. A pinned card is a GIF played by a
browser on a surface we do not control, so the delay floor, the dither and the
palette cap are all properties of that player rather than preferences.

Tests that shell out to ffmpeg are skipped without it; the rest run anywhere.
"""
import pathlib
import shutil
import subprocess

import pytest

from tools.brains import encode, figures

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "two-colour-transparent.gif"
needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="no ffmpeg")


def pngs(n, size=32):
    """`n` frames of a bar sliding one pixel per frame, on transparency.

    The bar carries a two-pixel antialiased fringe, in roughly the proportion a
    browser's 4x downscale of an 8px stroke leaves: solid accent dominating, a
    thin softened edge. Both halves matter — flat frames would make any palette
    cap look like one visible colour, and a fringe-heavy bar would drag
    `palettegen`'s single slot to the average of the three tones instead of the
    accent.
    """
    import struct
    import zlib

    def px(x, y, i):
        if not 8 <= y < 24:
            return (0, 0, 0, 0)
        if i <= x < i + 20:
            return (239, 99, 6, 255)
        if x == i + 20:
            return (247, 160, 96, 255)
        if x == i + 21:
            return (252, 214, 184, 255)
        return (0, 0, 0, 0)

    out = []
    for i in range(n):
        rows = [[px(x, y, i) for x in range(size)] for y in range(size)]
        raw = b"".join(b"\x00" + bytes(v for p in row for v in p) for row in rows)

        def chunk(tag, data):
            return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

        out.append(
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b"")
        )
    return out


@pytest.fixture
def out(tmp_path):
    return tmp_path / "out.gif"


@pytest.fixture
def encoded(out):
    # Every consumer carries `needs_ffmpeg`; a mark on a fixture is ignored.
    encode.gif(pngs(4), out, delay_cs=10)
    return out


def test_a_delay_below_the_honoured_floor_is_refused(out):
    """0 and 1 are clamped *up* to 100ms by both Chromium and Firefox: asking
    for the fastest frame rate gives you the slowest. 2cs is the real floor."""
    with pytest.raises(ValueError, match="2cs"):
        encode.gif(pngs(1), out, delay_cs=1)


def test_the_floor_itself_is_allowed(out):
    """Boundary: 2cs is honoured, so it must not be refused alongside 1."""
    with pytest.raises(RuntimeError):
        encode.gif(pngs(1), out, delay_cs=2, version=(5, 0))


def test_ffmpeg_below_six_is_refused(out):
    """`atkinson` does not exist before 6.0. Falling back to the next-cheapest
    dither would silently ship a GIF 25% larger, which is the kind of failure
    nobody notices until the card is already pinned."""
    with pytest.raises(RuntimeError, match=r"6\.0"):
        encode.gif(pngs(1), out, delay_cs=10, version=(5, 1))


def test_a_palette_too_small_to_reserve_transparency_is_refused(out):
    """ffmpeg rejects `max_colors=2` with `reserve_transparent=1` outright, and
    does it from inside the filter graph where the message is easy to miss."""
    with pytest.raises(ValueError, match="at least 3"):
        encode.gif(pngs(1), out, delay_cs=10, colours=2)


def test_encoding_nothing_is_refused(out):
    with pytest.raises(ValueError, match="no frames"):
        encode.gif([], out, delay_cs=10)


@needs_ffmpeg
def test_the_encoded_palette_is_one_visible_colour_and_one_transparent(encoded):
    """The whole theme story. One visible entry means the drawing is a single
    flat tone; the transparent index means GitHub's own surface — light or dark
    — shows through everywhere else.

    Which tone it is belongs to the drawing, not to the encoder:
    `stats_mode=diff` histograms only the pixels that change between frames, so
    a figure whose motion is all antialiased edge resolves its one slot to the
    average of that edge. `test_brains_build.py` is where the real figure's tone
    is held to the accent.
    """
    table, transparent = encode.palette(encoded)
    assert transparent is not None
    assert len(visible(table, transparent)) == 1


@needs_ffmpeg
def test_a_generous_palette_is_what_the_cap_is_for(out):
    """Re-encoding a two-colour reference GIF with `max_colors=32` grew it from
    117 KB to 291 KB. The drawing has one colour; the antialiased edge is the
    browser's, and dithering it against transparency is what keeps it one."""
    encode.gif(pngs(4), out, delay_cs=10, colours=32)
    table, transparent = encode.palette(out)
    assert len(visible(table, transparent)) > 1


@needs_ffmpeg
def test_the_gif_loops_forever(encoded):
    """`NETSCAPE2.0` is written whatever the loop count is, so the marker alone
    proves nothing — a count of 1 plays once and stops on the last frame."""
    assert b"NETSCAPE2.0" in encoded.read_bytes()
    assert encode.loops(encoded) == 0


def test_the_filter_chain_names_the_cheap_dither_and_reserves_transparency():
    """Neither survives into the output bytes, so the chain is the only place
    they can be checked. `atkinson` is 2% over no dither at all on flat vector
    art, where floyd_steinberg is 13% and bayer 25%."""
    chain = encode.chain(3)
    assert "dither=atkinson" in chain
    assert "max_colors=3:reserve_transparent=1" in chain
    assert "alpha_threshold=128" in chain


@needs_ffmpeg
@pytest.mark.parametrize("delay_cs", [2, 5, 10, 25])
def test_the_requested_delay_reaches_the_file(out, delay_cs):
    """ffmpeg is told a frame rate, not a delay, so the conversion is the thing
    that can be wrong — and at 10cs it is its own fixed point, which hides a
    conversion that does nothing. The values here are the exact ones: 50, 20,
    10 and 4 fps."""
    encode.gif(pngs(2), out, delay_cs=delay_cs)
    assert encode.delay(out) == delay_cs


@needs_ffmpeg
def test_the_frames_are_the_size_they_were_drawn_at(out):
    encode.gif(pngs(2), out, delay_cs=10)
    assert encode.size(out) == (32, 32)


def test_palette_reads_a_two_entry_table_from_a_known_gif():
    """Pinned against a committed fixture rather than against our own encoder,
    so a change in ffmpeg's output cannot quietly satisfy both sides at once."""
    table, transparent = encode.palette(FIXTURE)
    assert len(table) == 256
    assert transparent == 255
    assert visible(table, transparent) == {(0xEF, 0x63, 0x06)}
    assert encode.delay(FIXTURE) == 10


def test_palette_reports_no_transparency_when_a_gif_declares_none():
    """A GIF whose control block does not set the flag is opaque, and an opaque
    pin is a slab on one of the two themes."""
    raw = FIXTURE.read_bytes()
    i = raw.find(b"\x21\xf9\x04")
    opaque = raw[: i + 3] + bytes([raw[i + 3] & ~1]) + raw[i + 4 :]
    path = FIXTURE.parent / "opaque.gif"
    try:
        path.write_bytes(opaque)
        assert encode.palette(path)[1] is None
    finally:
        path.unlink()


def test_palette_rejects_something_that_is_not_a_gif(tmp_path):
    bad = tmp_path / "not.gif"
    bad.write_bytes(b"\x89PNG\r\n\x1a\n")
    with pytest.raises(ValueError, match="not a GIF"):
        encode.palette(bad)


def test_loops_rejects_a_gif_with_no_netscape_extension(tmp_path):
    """A GIF with no loop extension plays once. On a pinned card that is a
    drawing that moves for three seconds and then stops for good."""
    bad = tmp_path / "once.gif"
    bad.write_bytes(b"GIF89a" + bytes([16, 0, 16, 0, 0x80, 0, 0]) + b"\x00" * 6)
    with pytest.raises(ValueError, match="no loop count"):
        encode.loops(bad)


def test_delay_rejects_a_gif_with_no_control_block(tmp_path):
    """A GIF whose frames carry no delay plays as fast as the decoder can go,
    which on a pinned card is a flicker rather than a loop."""
    bad = tmp_path / "nodelay.gif"
    bad.write_bytes(b"GIF89a" + bytes([16, 0, 16, 0, 0x80, 0, 0]) + b"\x00" * 6)
    with pytest.raises(ValueError, match="no frame delay"):
        encode.delay(bad)


def test_palette_rejects_a_gif_with_no_global_table(tmp_path):
    bad = tmp_path / "local.gif"
    bad.write_bytes(b"GIF89a" + bytes([16, 0, 16, 0, 0x00, 0, 0]))
    with pytest.raises(ValueError, match="no global colour table"):
        encode.palette(bad)


@needs_ffmpeg
def test_ffmpeg_version_reports_the_installed_major_and_minor():
    major, minor = encode.ffmpeg_version()
    assert isinstance(major, int) and isinstance(minor, int)
    assert major >= 6, "this repo's floor; see tools/brains/README.md"


def test_ffmpeg_version_parses_the_banner():
    assert encode.parse_version("ffmpeg version 9.0.1 Copyright (c) 2000") == (9, 0)
    assert encode.parse_version("ffmpeg version n6.1.1-static") == (6, 1)
    assert encode.parse_version("ffmpeg version 2024-01-01-git-abc") is None


def test_a_missing_ffmpeg_is_an_error_naming_what_to_install(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: None)
    with pytest.raises(RuntimeError, match="ffmpeg"):
        encode.ffmpeg_version()


def test_an_unreadable_banner_is_an_error(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/ffmpeg")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Done("ffmpeg, the leading tool"))
    with pytest.raises(RuntimeError, match="version"):
        encode.ffmpeg_version()


class _Done:
    def __init__(self, stdout):
        self.stdout = stdout
        self.returncode = 0


def visible(table, transparent):
    """Distinct painted colours in a global table.

    ffmpeg always writes 256 entries, pads the unused ones with black, and
    parks its reserved transparent sentinel at the last index — so neither black
    nor the entry at `transparent` is paint. A second real colour appearing here
    is palette drift, which puts a dithered second tone on a card that has one.
    """
    return {c for i, c in enumerate(table) if i != transparent} - {(0, 0, 0)}


def test_the_accent_the_art_declares_is_the_one_the_encoder_must_keep():
    """Ties the two halves together: `figures.ACCENT` is a hex string and the
    palette is a byte triple, and nothing else in the suite would notice them
    drifting apart."""
    assert tuple(int(figures.ACCENT[i : i + 2], 16) for i in (1, 3, 5)) == (0xEF, 0x63, 0x06)
