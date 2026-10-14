"""Top slice: window chrome, name, role, tagline."""
from .. import console as c


def render(cfg, _data, theme):
    ident = cfg["identity"]
    name, handle = ident["name"], ident["handle"]
    role, tagline = ident["role"], ident["tagline"]

    y = 96
    body = [c.title_bar(theme)]

    prompt = (f'<text x="{c.TEXT_X}" y="{{y}}" class="mono dim">'
              f'<tspan>❯</tspan><tspan dx="8">whoami</tspan></text>')
    rows = [prompt, None]
    markup, y = c.stagger(rows, y, 26)
    body.append(markup)

    # The name is the one element at display size; everything else hangs off
    # its baseline.
    body.append(f'''<g class="ln" style="animation-delay:0.40s">
<text x="{c.TEXT_X}" y="{y + 28}" class="display ink">{c.e(name)}</text>
</g>''')
    y += 28 + 30

    body.append(f'''<g class="ln" style="animation-delay:0.52s">
<text x="{c.TEXT_X}" y="{y}" class="mono"><tspan class="dim">{c.e(handle)}</tspan><tspan class="dim" dx="10">·</tspan><tspan class="ink" dx="10">{c.e(role)}</tspan></text>
</g>''')
    y += 36

    lines = [f'<text x="{c.TEXT_X}" y="{{y}}" class="body dim">{c.e(line)}</text>'
             for line in tagline]
    markup, y = c.stagger(lines, y, 26, delay=0.56)
    body.append(markup)

    body.append(f'''<g class="ln" style="animation-delay:{0.56 + (len(tagline) + 1) * 0.12:.2f}s">
<text x="{c.TEXT_X}" y="{y + 14}" class="mono dim"><tspan>❯</tspan><tspan class="ink cursor" dx="10">▌</tspan></text>
</g>''')

    height = c.to_grid(y + 44)
    desc = f"{name} — {role}. " + " ".join(tagline)
    return c.slice_svg(
        theme, height, "\n".join(body),
        title=f"{name} ({handle})", desc=desc,
        text="❯▌·—", top=True,
    )
