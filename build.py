#!/usr/bin/env python3
"""Build the Zed themes "Cursor Dark" and "Cursor Light" from Cursor's own.

Run: python3 -I build.py [--check] [CURSOR_THEMES_DIR]

Reads Cursor's VS Code-format themes (default: the ones inside Cursor.app),
maps their workbench colours and token rules to Zed's theme keys with the
tables below, and writes both into themes/cursor.json. Every colour comes from
Cursor's files; the tables only choose which Cursor colour feeds which Zed key.
--check also fetches Zed's current theme keys from GitHub, fails on a key Zed
does not know or a malformed colour, and reports each syntax colour's contrast.
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "themes" / "cursor.json"
DEFAULT_DIR = Path("/Applications/Cursor.app/Contents/Resources/app/extensions/theme-cursor/themes")
# Zed theme name -> (appearance, Cursor's file in that folder).
THEMES = {
    "Cursor Dark": ("dark", "cursor-dark-color-theme.json"),
    "Cursor Light": ("light", "cursor-light-color-theme.json"),
}

# Zed UI key -> Cursor workbench keys, first one present wins.
UI = {
    "background": ["editor.background"],
    "surface.background": ["panel.background", "sideBar.background"],
    "elevated_surface.background": ["editorWidget.background", "editorHoverWidget.background"],
    "panel.background": ["sideBar.background", "panel.background"],
    "panel.overlay_background": ["sideBar.background"],
    "panel.overlay_hover": ["list.hoverBackground"],
    "panel.focused_border": ["list.focusOutline", "focusBorder"],
    "panel.indent_guide": ["tree.indentGuidesStroke", "editorIndentGuide.background1"],
    "panel.indent_guide_active": ["editorIndentGuide.activeBackground1"],
    "panel.indent_guide_hover": ["editorIndentGuide.activeBackground1"],
    "pane.focused_border": ["focusBorder"],
    "pane_group.border": ["editorGroup.border"],
    "title_bar.background": ["titleBar.activeBackground"],
    "title_bar.inactive_background": ["titleBar.inactiveBackground", "titleBar.activeBackground"],
    "status_bar.background": ["statusBar.background"],
    "toolbar.background": ["breadcrumb.background", "editor.background"],
    "tab_bar.background": ["editorGroupHeader.tabsBackground"],
    "tab.inactive_background": ["tab.inactiveBackground"],
    "tab.active_background": ["tab.activeBackground", "tab.inactiveBackground"],
    "drop_target.background": ["list.dropBackground"],

    "border": ["panel.border"],
    "border.variant": ["editorGroup.border", "sideBar.border"],
    "border.focused": ["focusBorder"],
    "border.selected": ["focusBorder"],
    "border.disabled": ["panel.border"],

    "element.background": ["button.secondaryBackground"],
    "element.hover": ["list.hoverBackground"],
    "element.active": ["inputOption.activeBackground", "list.focusBackground"],
    "element.selected": ["list.focusBackground", "list.activeSelectionBackground"],
    "element.selection_background": ["editor.selectionBackground"],
    "element.disabled": ["list.inactiveSelectionBackground"],
    "ghost_element.hover": ["list.hoverBackground"],
    "ghost_element.active": ["inputOption.activeBackground", "list.focusBackground"],
    "ghost_element.selected": ["list.focusBackground", "list.activeSelectionBackground"],

    "text": ["foreground"],
    "text.muted": ["descriptionForeground", "tab.inactiveForeground"],
    "text.placeholder": ["input.placeholderForeground"],
    "text.disabled": ["disabledForeground", "editorLineNumber.foreground"],
    "text.accent": ["list.highlightForeground"],
    "link_text.hover": ["textLink.activeForeground"],
    "icon": ["icon.foreground", "foreground"],
    "icon.muted": ["editorLineNumber.foreground"],
    "icon.disabled": ["input.placeholderForeground"],
    "icon.placeholder": ["input.placeholderForeground"],
    "icon.accent": ["textLink.foreground"],

    "scrollbar.thumb.background": ["scrollbarSlider.background"],
    "scrollbar.thumb.hover_background": ["scrollbarSlider.hoverBackground"],
    "scrollbar.thumb.active_background": ["scrollbarSlider.activeBackground"],
    "scrollbar.track.border": ["editorOverviewRuler.border"],
    "minimap.thumb.background": ["minimapSlider.background", "scrollbarSlider.background"],
    "minimap.thumb.hover_background": ["minimapSlider.hoverBackground", "scrollbarSlider.hoverBackground"],
    "minimap.thumb.active_background": ["minimapSlider.activeBackground", "scrollbarSlider.activeBackground"],

    "editor.foreground": ["editor.foreground"],
    "editor.background": ["editor.background"],
    "editor.gutter.background": ["editorGutter.background", "editor.background"],
    "editor.subheader.background": ["sideBarSectionHeader.background", "sideBar.background"],
    "editor.active_line.background": ["editor.lineHighlightBackground"],
    "editor.highlighted_line.background": ["editor.rangeHighlightBackground"],
    "editor.line_number": ["editorLineNumber.foreground"],
    "editor.active_line_number": ["editorLineNumber.activeForeground", "editor.foreground"],
    "editor.hover_line_number": ["editorLineNumber.activeForeground"],
    "editor.invisible": ["editorWhitespace.foreground"],
    "editor.wrap_guide": ["editorRuler.foreground"],
    "editor.active_wrap_guide": ["editorRuler.foreground"],
    "editor.indent_guide": ["editorIndentGuide.background1"],
    "editor.indent_guide_active": ["editorIndentGuide.activeBackground1"],
    "editor.document_highlight.read_background": ["editor.wordHighlightBackground"],
    "editor.document_highlight.write_background": ["editor.wordHighlightStrongBackground"],
    "editor.document_highlight.bracket_background": ["editorBracketMatch.background"],
    "editor.code_lens.foreground": ["editorCodeLens.foreground"],
    "search.match_background": ["editor.findMatchHighlightBackground"],
    "search.active_match_background": ["editor.findMatchBackground"],

    "terminal.background": ["terminal.background"],
    "terminal.foreground": ["terminal.foreground"],
    "terminal.bright_foreground": ["terminal.foreground"],
    "terminal.dim_foreground": ["terminal.ansiBrightBlack"],
    "terminal.ansi.background": ["terminal.background"],

    "version_control.added": ["editorGutter.addedBackground"],
    "version_control.modified": ["editorGutter.modifiedBackground"],
    "version_control.deleted": ["editorGutter.deletedBackground"],
    "version_control.renamed": ["gitDecoration.renamedResourceForeground", "gitDecoration.untrackedResourceForeground"],
    "version_control.conflict": ["gitDecoration.conflictingResourceForeground", "terminal.ansiMagenta"],
    "version_control.ignored": ["gitDecoration.ignoredResourceForeground"],
    "version_control.word_added": ["diffEditor.insertedTextBackground"],
    "version_control.word_deleted": ["diffEditor.removedTextBackground"],
    "version_control.conflict_marker.ours": ["merge.currentHeaderBackground"],
    "version_control.conflict_marker.theirs": ["merge.incomingHeaderBackground"],
}

# The 16 ANSI colours, by name, from terminal.ansi<Name> / ansiBright<Name>.
ANSI = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]

# Zed status colour -> Cursor workbench keys; each gets .background (the
# colour at STATUS_ALPHA) and .border (the colour), as Cursor Dark for Zed does.
STATUS = {
    "error": ["editorError.foreground"],
    "warning": ["editorWarning.foreground"],
    "info": ["editorInfo.foreground", "textLink.foreground"],
    "hint": ["editorInlayHint.foreground"],
    "success": ["gitDecoration.addedResourceForeground"],
    "created": ["gitDecoration.addedResourceForeground"],
    "modified": ["gitDecoration.modifiedResourceForeground"],
    "deleted": ["gitDecoration.deletedResourceForeground"],
    "renamed": ["gitDecoration.renamedResourceForeground", "gitDecoration.untrackedResourceForeground"],
    "conflict": ["gitDecoration.conflictingResourceForeground", "terminal.ansiMagenta"],
    "ignored": ["gitDecoration.ignoredResourceForeground"],
    "hidden": ["gitDecoration.ignoredResourceForeground"],
    "unreachable": ["gitDecoration.ignoredResourceForeground"],
    "predictive": ["editorGhostText.foreground", "editorLineNumber.foreground"],
}
STATUS_ALPHA = "22"
# Exceptions where Cursor gives a background of its own.
STATUS_BACKGROUND = {"error": ["inputValidation.errorBackground"], "hint": ["editorInlayHint.background"]}

# Players: the first is the user (Cursor's cursor and selection); the others
# take Cursor's syntax and terminal colours.
PLAYER_COLOURS = ["terminal.ansiBlue", "terminal.ansiGreen", "terminal.ansiMagenta",
                  "editorWarning.foreground", "terminal.ansiCyan", "terminal.ansiRed"]
PLAYER_SELECTION_ALPHA = "33"

# Zed capture -> the TextMate scope a typical grammar gives that construct.
# Cursor's rules are matched against it as VS Code does: a rule applies when
# its selector is a dot-prefix of the scope, the most specific selector wins
# each property, a later rule wins a tie. A capture whose scope no rule
# styles is left out and takes editor.foreground.
SYNTAX = {
    "comment": "comment.line.double-slash",
    "comment.doc": "comment.block.documentation",
    "string": "string.quoted.double",
    "string.escape": "constant.character.escape",
    "string.regex": "string.regexp",
    "string.special.symbol": "constant.other.symbol",
    "text.literal": "markup.inline.raw.string.markdown",
    "keyword": "keyword.control",
    "keyword.declaration": "storage.type",
    "keyword.operator": "keyword.operator.expression.typeof",
    "keyword.preproc": "keyword.control.directive.include",
    "keyword.directive": "keyword.control.directive.include",
    "preproc": "keyword.control.directive.include",
    "operator": "keyword.operator.assignment",
    "function": "entity.name.function",
    "type": "entity.name.type",
    "type.builtin": "support.type.primitive",
    "enum": "entity.name.type.enum",
    "constructor": "entity.name.type.class",
    "constant": "variable.other.constant",
    "constant.builtin": "constant.language.null",
    "boolean": "constant.language.boolean.true",
    "number": "constant.numeric.decimal",
    "variable": "variable.other.readwrite",
    "variable.parameter": "variable.parameter",
    "variable.special": "variable.language.this",
    "variable.builtin": "variable.language.this",
    "property": "variable.other.property",
    "property.json_key": "support.type.property-name.json",
    "attribute": "entity.other.attribute-name",
    "tag": "entity.name.tag.html",
    "label": "entity.name.label",
    "namespace": "entity.name.namespace",
    "module": "entity.name.namespace",
    "variant": "variable.other.enummember",
    "lifetime": "storage.modifier.lifetime",
    "punctuation": "punctuation.separator.comma",
    "punctuation.special": "punctuation.definition.template-expression.begin",
    "punctuation.list_marker": "punctuation.definition.list.begin.markdown",
    "punctuation.markup": "punctuation.definition.bold.markdown",
    "punctuation.bracket.jsx": "punctuation.definition.tag.begin",
    "embedded": "meta.template.expression",
    "title": "markup.heading.markdown",
    "markup.heading": "markup.heading.markdown",
    "emphasis": "markup.italic.markdown",
    "emphasis.strong": "markup.bold.markdown",
    "link_text": "string.other.link.title.markdown",
    "link_uri": "markup.underline.link.markdown",
    "markup.link.url": "markup.underline.link.markdown",
    "diff.plus": "markup.inserted.diff",
    "diff.minus": "markup.deleted.diff",
    "diff.delta": "markup.changed.diff",
    "selector.class": "entity.other.attribute-name.class.css",
    "selector.id": "entity.other.attribute-name.id.css",
    "selector.pseudo": "entity.other.attribute-name.pseudo-class.css",
}
# Zed-only syntax keys fed by workbench colours.
SYNTAX_FROM_UI = {"hint": (["editorInlayHint.foreground"], None),
                  "predictive": (["editorGhostText.foreground", "editorLineNumber.foreground"], "italic")}


def strip_jsonc(text):
    out, i, n, in_string = [], 0, len(text), False
    while i < n:
        c = text[i]
        if in_string:
            out.append(c)
            if c == "\\":
                out.append(text[i + 1]); i += 2; continue
            if c == '"':
                in_string = False
            i += 1; continue
        if c == '"':
            in_string = True
        elif text.startswith("//", i):
            j = text.find("\n", i); i = n if j < 0 else j; continue
        elif text.startswith("/*", i):
            j = text.find("*/", i); i = n if j < 0 else j + 2; continue
        out.append(c); i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def norm(colour):
    h = colour.strip().lstrip("#").upper()
    if len(h) in (3, 4):
        h = "".join(ch * 2 for ch in h)
    return "#" + (h[:6] if h[6:] == "FF" else h)


def pick(colors, keys):
    for k in keys:
        v = colors.get(k)
        if isinstance(v, str) and v.startswith("#"):
            return norm(v)
    return None


def with_alpha(colour, alpha):
    return colour[:7] + alpha


def build(source):
    vs = json.loads(strip_jsonc(source.read_text()))
    colors = vs["colors"]
    style, missing = {"background.appearance": "opaque"}, []

    for key, keys in UI.items():
        v = pick(colors, keys)
        if v: style[key] = v
        else: missing.append(key)
    for t in ("border.transparent", "ghost_element.background", "ghost_element.disabled",
              "scrollbar.thumb.border", "scrollbar.track.background", "minimap.thumb.border"):
        style[t] = "#00000000"
    for name in ANSI:
        cap = name.capitalize()
        normal, bright = pick(colors, [f"terminal.ansi{cap}"]), pick(colors, [f"terminal.ansiBright{cap}"])
        style[f"terminal.ansi.{name}"] = normal
        style[f"terminal.ansi.bright_{name}"] = bright
        style[f"terminal.ansi.dim_{name}"] = normal
    for key, keys in STATUS.items():
        v = pick(colors, keys)
        if not v:
            missing.append(key); continue
        style[key] = v
        style[f"{key}.background"] = pick(colors, STATUS_BACKGROUND.get(key, [])) or with_alpha(v, STATUS_ALPHA)
        style[f"{key}.border"] = v
    style["debugger.accent"] = style["error"]

    cursor = pick(colors, ["editorCursor.foreground"])
    players = [{"cursor": cursor, "background": cursor, "selection": pick(colors, ["editor.selectionBackground"])}]
    for k in PLAYER_COLOURS:
        c = pick(colors, [k])
        players.append({"cursor": c, "background": c, "selection": with_alpha(c, PLAYER_SELECTION_ALPHA)})
    style["players"] = players
    style["accents"] = [p["cursor"] for p in players[1:]]

    # (selector, order, settings) for every single-scope selector.
    rules = []
    for order, t in enumerate(vs.get("tokenColors", [])):
        sc = t.get("scope")
        selectors = sc if isinstance(sc, list) else (sc.split(",") if sc else [])
        for sel in (x.strip() for x in selectors):
            if sel and " " not in sel:
                rules.append((sel, order, t.get("settings", {})))

    def token_style(scope):
        best = {}
        for sel, order, settings in rules:
            if scope != sel and not scope.startswith(sel + "."):
                continue
            rank = (sel.count(".") + 1, order)
            for prop in ("foreground", "fontStyle"):
                if prop in settings and (prop not in best or rank > best[prop][0]):
                    best[prop] = (rank, settings[prop])
        return {k: v for k, (_, v) in best.items()}

    syntax = {}
    for key, scope in SYNTAX.items():
        s = token_style(scope)
        entry = {}
        if s.get("foreground"): entry["color"] = norm(s["foreground"])
        fs = s.get("fontStyle", "") or ""
        if "italic" in fs: entry["font_style"] = "italic"
        if "bold" in fs: entry["font_weight"] = 700
        if entry: syntax[key] = entry
        else: missing.append(f"syntax.{key}")
    for key, (keys, font_style) in SYNTAX_FROM_UI.items():
        v = pick(colors, keys)
        if v:
            syntax[key] = {"color": v, **({"font_style": font_style} if font_style else {})}
    style["syntax"] = syntax
    return style, missing


def luminance(h):
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def blend(fg, bg):
    a = int(fg[7:9], 16) / 255 if len(fg) == 9 else 1
    return "#" + "".join(f"{round(int(fg[i:i+2], 16) * a + int(bg[i:i+2], 16) * (1 - a)):02X}" for i in (1, 3, 5))


def contrast(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def check(family):
    url = "https://raw.githubusercontent.com/zed-industries/zed/main/crates/settings_content/src/theme.rs"
    with urllib.request.urlopen(url, timeout=30) as r:
        known = set(re.findall(r'rename = "([a-z_.0-9]+)"', r.read().decode()))
    known |= {"accents", "players", "syntax", "background.appearance"}
    ok = True
    for theme in family["themes"]:
        style = theme["style"]
        unknown = sorted(set(style) - known)
        bad = [(k, v) for k, v in style.items() if isinstance(v, str) and k != "background.appearance"
               and not re.match(r"^#[0-9A-F]{6}([0-9A-F]{2})?$", v)]
        bg = style["editor.background"]
        print(f"{theme['name']}: syntax contrast on the editor (Cursor's colours, reported, not enforced)")
        for k, v in sorted(style["syntax"].items()):
            if "color" in v:
                print(f"  {k:28} {v['color']:10} {contrast(blend(v['color'], bg), bg):4.1f}")
        for s in ("background", "panel.background", "elevated_surface.background", "title_bar.background"):
            print(f"  text on {s:28} {contrast(blend(style['text'], style[s]), style[s]):4.1f}")
        for k in unknown: print("FAIL unknown key (Zed ignores it):", k)
        for k, v in bad: print("FAIL malformed colour:", k, v)
        ok = ok and not unknown and not bad
    return ok


def main():
    args = [a for a in sys.argv[1:] if a != "--check"]
    folder = Path(args[0]) if args else DEFAULT_DIR
    family = {"$schema": "https://zed.dev/schema/themes/v0.2.0.json", "name": "Cursor",
              "author": "Renaud Denis <mail@renauddenis.com>", "themes": []}
    for name, (appearance, filename) in THEMES.items():
        style, missing = build(folder / filename)
        family["themes"].append({"name": name, "appearance": appearance, "style": style})
        if missing: print(f"{name}: not styled by Cursor, left to Zed's defaults:", ", ".join(missing))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(family, indent=2) + "\n")
    print(f"wrote {OUT.relative_to(HERE)} from {folder}")
    if "--check" in sys.argv:
        sys.exit(0 if check(family) else 1)


if __name__ == "__main__":
    main()
