"""
APCA (Accessible Perceptual Contrast Algorithm) implementation.
Ported from the official JS reference: apca-w3 v0.0.98G.
"""

from playwright.sync_api import Page

from accessibility_sweep.models import Issue, Severity


def srgb_to_y(hex_color: str) -> float:
    """Convert hex colour to APCA luminance value."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16) / 255
    g = int(hex_color[2:4], 16) / 255
    b = int(hex_color[4:6], 16) / 255

    # Linearise
    r = pow(r, 2.4)
    g = pow(g, 2.4)
    b = pow(b, 2.4)

    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b

    # Black clamp
    if y < 0.022:
        y += pow(0.022 - y, 1.414)

    return y


def apca_contrast(text_hex: str, bg_hex: str) -> float:
    """
    Returns APCA Lc contrast value.
    Positive = dark text on light background.
    Negative = light text on dark background.
    Absolute value used for pass/fail evaluation.
    """
    y_text = srgb_to_y(text_hex)
    y_bg = srgb_to_y(bg_hex)

    c = 1.14

    if y_bg > y_text:
        c *= pow(y_bg, 0.56) - pow(y_text, 0.57)
    else:
        c *= pow(y_bg, 0.65) - pow(y_text, 0.62)

    if abs(c) < 0.1:
        return 0.0
    elif c > 0:
        c -= 0.027
    else:
        c += 0.027

    return round(c * 100, 2)


def apca_passes(lc_value: float, font_size_px: float, font_weight: int) -> bool:
    """
    Basic APCA pass/fail for body text.
    Reference: apca-w3 fluent readability table.
    """
    lc = abs(lc_value)
    if font_size_px >= 24 and font_weight >= 300:
        return lc >= 60
    elif font_size_px >= 18.66 and font_weight >= 700:
        return lc >= 60
    else:
        return lc >= 75  # Body text default


def _rgb_to_hex(rgb_str: str) -> str | None:
    """Parse 'rgb(r, g, b)' or 'rgba(r, g, b, a)' to '#rrggbb'. Returns None on failure."""
    rgb_str = rgb_str.strip()
    if rgb_str.startswith("rgba("):
        inner = rgb_str[5:].rstrip(")")
    elif rgb_str.startswith("rgb("):
        inner = rgb_str[4:].rstrip(")")
    else:
        if rgb_str.startswith("#") and len(rgb_str) in (4, 7):
            return rgb_str
        return None

    parts = [p.strip() for p in inner.split(",")]
    if len(parts) < 3:
        return None
    try:
        r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
        return f"#{r:02x}{g:02x}{b:02x}"
    except ValueError:
        return None


def check_apca_contrast(page: Page) -> list[Issue]:
    """
    Sample text elements on the page and check APCA contrast.
    Uses Playwright to get computed styles.
    """
    issues = []

    elements = page.evaluate("""
    () => {
        const selectors = 'p, span, a, li, h1, h2, h3, h4, h5, h6, label, button, td, th';
        const els = document.querySelectorAll(selectors);
        const results = [];
        const seen = new Set();
        for (const el of els) {
            if (!el.textContent.trim()) continue;
            const style = window.getComputedStyle(el);
            const color = style.color;
            const bg = style.backgroundColor;
            const fontSize = parseFloat(style.fontSize);
            const fontWeight = parseInt(style.fontWeight) || 400;
            const key = `${color}|${bg}|${fontSize}|${fontWeight}`;
            if (seen.has(key)) continue;
            seen.add(key);
            results.push({
                selector: el.tagName.toLowerCase() +
                    (el.id ? '#' + el.id : '') +
                    (el.className ? '.' + String(el.className).split(' ')[0] : ''),
                color: color,
                backgroundColor: bg,
                fontSize: fontSize,
                fontWeight: fontWeight,
                text: el.textContent.trim().substring(0, 50)
            });
            if (results.length >= 100) break;
        }
        return results;
    }
    """)

    for el in elements:
        fg_hex = _rgb_to_hex(el["color"])
        bg_hex = _rgb_to_hex(el["backgroundColor"])
        if not fg_hex or not bg_hex:
            continue
        # Skip transparent / rgba(0,0,0,0) backgrounds
        if el["backgroundColor"].startswith("rgba") and el["backgroundColor"].endswith(", 0)"):
            continue

        lc = apca_contrast(fg_hex, bg_hex)
        if not apca_passes(lc, el["fontSize"], el["fontWeight"]):
            issues.append(Issue(
                type="apca_contrast",
                element=el["selector"],
                description=(
                    f"APCA contrast Lc {lc} is below threshold for "
                    f"{el['fontSize']}px / weight {el['fontWeight']}. "
                    f"Text: \"{el['text']}\""
                ),
                wcag_criterion="1.4.3",
                severity=Severity.MAJOR,
                recommendation=(
                    f"Increase contrast between text ({fg_hex}) and background ({bg_hex}). "
                    f"Target Lc >= 75 for body text or Lc >= 60 for large text."
                ),
                source="WCAG 2.2",
            ))

    return issues
