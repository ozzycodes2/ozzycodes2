"""Top slice: window chrome, name, role, tagline."""
from .. import console as c


def render(cfg, _data):
    ident = cfg["identity"]
    name, handle = ident["name"], ident["handle"]
    role, tagline = ident["role"], ident["tagline"]

    y = 96
    body = [c.title_bar(56)]

    prompt = (f'<text x="{c.TEXT_X}" y="{{y}}" style="font-size:14px">'
              f'<tspan class="ok">❯</tspan><tspan class="dim" dx="8">whoami</tspan></text>')
    rows = [prompt, None]
    markup, y = c.stagger(rows, y, 26)
    body.append(markup)

    # The name is the one oversized element; everything else hangs off its baseline.
    body.append(f'''<g class="ln" style="animation-delay:0.40s">
<text x="{c.TEXT_X}" y="{y + 26}" font-weight="700" fill="{c.ACCENT}" filter="url(#soft)" opacity=".7" style="font-size:38px">{c.e(name)}</text>
<text x="{c.TEXT_X}" y="{y + 26}" font-weight="700" class="wh" style="font-size:38px">{c.e(name)}</text>
</g>''')
    y += 26 + 30

    body.append(f'''<g class="ln" style="animation-delay:0.52s">
<text x="{c.TEXT_X}" y="{y}" style="font-size:15px"><tspan class="alt">{c.e(handle)}</tspan><tspan class="faint" dx="10">·</tspan><tspan class="ac" dx="10">{c.e(role)}</tspan></text>
</g>''')
    y += 36

    lines = [f'<text x="{c.TEXT_X}" y="{{y}}" class="fg" style="font-size:15px">{c.e(line)}</text>'
             for line in tagline]
    markup, y = c.stagger(lines, y, 24, delay=0.56)
    body.append(markup)

    body.append(f'''<g class="ln" style="animation-delay:{0.56 + (len(tagline) + 1) * 0.12:.2f}s">
<text x="{c.TEXT_X}" y="{y + 14}" style="font-size:14px"><tspan class="ok">❯</tspan><tspan class="wh cursor" dx="10">█</tspan></text>
</g>''')

    height = c.to_grid(y + 44)
    desc = f"{name} — {role}. " + " ".join(tagline)
    return c.slice_svg(
        height, "\n".join(body),
        title=f"{name} ({handle})", desc=desc,
        text="❯█·—", top=True,
    )
