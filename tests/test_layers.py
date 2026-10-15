"""The dependency rule, checked rather than documented.

    sources/    may import nothing of the other two
    transform/  may import neither of the other two
    present/    may import transform/, never sources/
    entrypoints may import all three — they are the only place the layers meet

So the derivation can be tested against literals, panels cannot reach for data,
and the one place a request is made is the one place a credential appears.

`present/fonts.py` opens the vendored woff2 faces beside it, which is the single
file read above the data layer. They are code-adjacent resources pinned to the
renderer, not data: decoupling them would mean threading a loader through
`slice_svg` and every panel that calls it, to defer a read whose result cannot
vary. `test_file_reads_live_in_the_data_layer` holds that line at one file.
"""
import ast
import pathlib

import pytest

PROFILE = pathlib.Path(__file__).resolve().parent.parent / "tools" / "profile"
LAYERS = ("sources", "transform", "present")
ENTRYPOINTS = ("fetch.py", "render.py", "readme.py", "preview.py")

# The only module above the data layer allowed to open a file. See the docstring.
READS_ITS_OWN_RESOURCES = PROFILE / "present" / "fonts.py"


def modules(layer):
    return sorted((PROFILE / layer).rglob("*.py"))


def imports(path):
    """Every `tools.profile` layer this module pulls in, by layer name.

    Catches both spellings — `from ..transform import x` by its level, and
    `from tools.profile.transform import x` by its dotted name.
    """
    found = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom):
            name = node.module or ""
            if node.level:
                # Relative: the first segment names a sibling package when the
                # import climbs out of this module's own package.
                parts = name.split(".")
                found.update(p for p in parts[:1] if p in LAYERS)
                if node.level >= 2 and not name:
                    found.update(a.name for a in node.names if a.name in LAYERS)
            else:
                found.update(p for p in name.split(".") if p in LAYERS)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                found.update(p for p in alias.name.split(".") if p in LAYERS)
    return found


@pytest.mark.parametrize("path", modules("transform"), ids=lambda p: p.name)
def test_transform_imports_neither_of_the_other_layers(path):
    """Pure derivation. Nothing here may fetch, read, or draw."""
    assert imports(path) - {"transform"} == set()


@pytest.mark.parametrize("path", modules("sources"), ids=lambda p: p.name)
def test_sources_import_neither_of_the_other_layers(path):
    """I/O only. A source that transforms cannot be re-derived from its output."""
    assert imports(path) - {"sources"} == set()


@pytest.mark.parametrize("path", modules("present"), ids=lambda p: p.name)
def test_present_never_imports_the_data_layer(path):
    """Panels draw what they are handed; they never reach for it."""
    assert "sources" not in imports(path), f"{path.name} imports the data layer"


@pytest.mark.parametrize("path", modules("present") + modules("transform"),
                         ids=lambda p: p.name)
def test_file_reads_live_in_the_data_layer(path):
    if path == READS_ITS_OWN_RESOURCES:
        pytest.skip("vendored typefaces — see this module's docstring")
    source = path.read_text()
    for forbidden in ("read_text", "read_bytes", "write_text", "write_bytes"):
        assert forbidden not in source, f"{path.name} does its own I/O"


NETWORK = {"urllib", "requests", "httpx", "http", "socket", "ssl"}


def imported_roots(path):
    """The top-level name of every module this one imports absolutely."""
    roots = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level:
            roots.add((node.module or "").split(".")[0])
    return roots


@pytest.mark.parametrize("path", modules("present") + modules("transform"),
                         ids=lambda p: p.name)
def test_nothing_above_the_data_layer_reaches_the_network(path):
    assert imported_roots(path) & NETWORK == set(), f"{path.name} reaches the network"


def test_the_data_layer_is_the_only_place_a_request_is_made():
    reaching = [p.name for p in modules("sources") if imported_roots(p) & NETWORK]
    assert reaching == ["github.py"]


@pytest.mark.parametrize("name", ENTRYPOINTS)
def test_every_entrypoint_is_wiring_and_not_logic(name):
    """An entrypoint that grows a derivation has put it back where it was."""
    tree = ast.parse((PROFILE / name).read_text())
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    assert functions, name
    for fn in functions:
        assert len(fn.body) <= 14, f"{name}:{fn.name} is doing real work"


@pytest.mark.parametrize("name", ENTRYPOINTS)
def test_every_entrypoint_exposes_a_main(name):
    tree = ast.parse((PROFILE / name).read_text())
    assert any(isinstance(n, ast.FunctionDef) and n.name == "main" for n in tree.body)


def test_the_panels_live_in_the_presentation_layer():
    assert (PROFILE / "present" / "panels").is_dir()
    assert not (PROFILE / "panels").exists()


def test_the_data_directory_is_not_a_python_package():
    """`data/` holds the committed JSON; the data *layer* is `sources/`."""
    assert (PROFILE / "data").is_dir()
    assert not (PROFILE / "data" / "__init__.py").exists()
