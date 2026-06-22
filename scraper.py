"""
Scraper del Mundial 2026
Lee la tabla de posiciones pública y genera data.json
con el mismo formato que usa la app HTML.

Este sitio carga sus datos con JavaScript (es una app Next.js), por lo
que no basta con una petición HTTP simple: usamos Playwright para
abrir un navegador headless, dejar que la página cargue, y luego
extraer el HTML ya renderizado.

Uso: python scraper.py
Genera/actualiza: data.json
"""

import json
import re
import sys
from datetime import datetime, timezone

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

SOURCE_URL = "https://bracketmundial2026.com/posiciones"
OUTPUT_FILE = "data.json"

# Mapeo de nombres de equipo en el sitio -> nombre que usa la app
NAME_MAP = {
    "Bosnia y Herzegovina": "Bosnia y Herz.",
    "República Checa": "R. Checa",
    "Chequia": "R. Checa",
    "Sudáfrica": "Sudáfrica",
    "Arabia Saudita": "Arabia Saudí",
    "Republica Democratica del Congo": "R.D. Congo",
    "DR Congo": "R.D. Congo",
    "Nueva Zelanda": "Nva. Zelanda",
    "Turquía": "Türkiye",
    "Iraq": "Irak",
}


def normalize_name(name: str) -> str:
    name = name.strip()
    return NAME_MAP.get(name, name)


def fetch_rendered_html(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent="Mozilla/5.0 (compatible; Mundial2026Bot/1.0)")
        page.goto(url, wait_until="networkidle", timeout=30000)
        # Espera extra por si algún dato tarda en pintarse tras el JS inicial
        page.wait_for_timeout(1500)
        html = page.content()
        browser.close()
        return html


def parse_groups(html: str) -> dict:
    """
    Busca cada bloque 'Posiciones Grupo X' y extrae su tabla
    (Equipo, J, V, E, D, GF, GC, DG, Pts).
    Devuelve {"A": [["México",2,2,0,0,3,0], ...], "B": [...], ...}
    """
    soup = BeautifulSoup(html, "html.parser")
    result = {}

    headings = soup.find_all(
        ["h1", "h2", "h3", "h4"], string=re.compile(r"Posiciones Grupo [A-L]")
    )
    if not headings:
        # Fallback: el texto puede estar repartido en hijos (ej. dentro de un <a>)
        headings = [
            tag
            for tag in soup.find_all(["h1", "h2", "h3", "h4"])
            if re.search(r"Posiciones Grupo [A-L]", tag.get_text())
        ]

    for heading in headings:
        match = re.search(r"Grupo ([A-L])", heading.get_text())
        if not match:
            continue
        group_letter = match.group(1)

        table = heading.find_next("table")
        if table is None:
            continue

        rows = table.find_all("tr")[1:]  # saltar encabezado
        teams = []
        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) < 8:
                continue
            raw_name = cells[0].get_text(strip=True)
            clean_name = re.sub(r"^[0-9]+", "", raw_name)
            clean_name = clean_name.replace("ANF", "").strip()
            clean_name = normalize_name(clean_name)

            try:
                pj = int(cells[1].get_text(strip=True))
                pg = int(cells[2].get_text(strip=True))
                pe = int(cells[3].get_text(strip=True))
                pp = int(cells[4].get_text(strip=True))
                gf = int(cells[5].get_text(strip=True))
                gc = int(cells[6].get_text(strip=True))
            except ValueError:
                continue

            teams.append([clean_name, pj, pg, pe, pp, gf, gc])

        if len(teams) == 4:
            result[group_letter] = teams

    return result


def main():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Renderizando {SOURCE_URL} con navegador headless ...")
    html = fetch_rendered_html(SOURCE_URL)

    groups = parse_groups(html)
    if len(groups) != 12:
        print(f"AVISO: se esperaban 12 grupos, se encontraron {len(groups)}.")
        print("El sitio puede haber cambiado de estructura. Revisa el scraper.")
        # Guardamos el HTML renderizado para poder depurar si algo falla
        with open("debug_rendered.html", "w", encoding="utf-8") as f:
            f.write(html)
        if len(groups) == 0:
            sys.exit(1)

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE_URL,
        "groups": groups,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"OK: {OUTPUT_FILE} actualizado con {len(groups)} grupos.")


if __name__ == "__main__":
    main()

