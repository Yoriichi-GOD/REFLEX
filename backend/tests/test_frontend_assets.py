"""Serve the studio's static dependencies through the real API mount order."""

import re


def test_studio_styles_images_and_fonts_are_reachable(client):
    page = client.get("/")
    assert page.status_code == 200
    stylesheet = re.search(r'href="([^\"]+\.css[^\"]*)"', page.text)
    assert stylesheet, "The studio must load its stylesheet."
    styles = client.get(stylesheet.group(1))
    assert styles.status_code == 200
    assets = set(re.findall(r"url\(['\"]?(/[^)'\"]+)", styles.text))
    fonts = [path for path in assets if path.endswith(".woff2")]
    assert len(fonts) == 3
    for path in assets:
        response = client.get(path)
        assert response.status_code == 200, f"Static asset is shadowed or missing: {path}"
        if path.endswith(".woff2"):
            assert response.content.startswith(b"wOF2"), path
        elif path.endswith(".webp"):
            assert response.content[:4] == b"RIFF" and response.content[8:12] == b"WEBP", path
