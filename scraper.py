"""
Scraper del Mundial 2026
Lee la tabla de posiciones pública y genera data.json
con el mismo formato que usa la app HTML.

Uso: python scraper.py
Genera/actualiza: data.json
"""

import json
import re
import sys
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

SOURCE_URL = "https://bracketmundial2026.com/posiciones"
OUTPUT_FILE = "data.json"

# Mapeo de nombres de equipo en el sitio -> nombre que usa la app
# (ajusta aquí si el sitio cambia algún nombre)
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
}


def normalize_name(name: str) -> str:
    name = name.strip()
    return NAME_MAP.get(name, name)


def fetch_html(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Mundial2026Bot/1.0; +https://github.com/)"
    }
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.text


def parse_groups(html: str) -> dict:
    """
    Busca cada bloque 'Posiciones Grupo X' y extrae su tabla
    (Equipo, J, V, E, D, GF, GC, DG, Pts).
    Devuelve {"A": [["México",2,2,0,0,3,0], ...], "B": [...], ...}
    """
    soup = BeautifulSoup(html, "html.parser")
    result = {}

    headings = soup.find_all(["h2", "h3"], string=re.compile(r"Posiciones Grupo [A-L]"))

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
            # quitar etiquetas tipo "ANF" (anfitrión) y numeros de posicion pegados
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


def parse_scorers(html: str) -> list:
    """
    Best-effort: el sitio fuente no siempre publica goleadores en esta página.
    Si no se encuentra nada, se devuelve lista vacía y la app conserva
    la última tabla de goleadores guardada.
    """
    return []


def main():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Descargando {SOURCE_URL} ...")
    html = fetch_html(SOURCE_URL)

    groups = parse_groups(html)
    if len(groups) != 12:
        print(f"AVISO: se esperaban 12 grupos, se encontraron {len(groups)}.")
        print("El sitio puede haber cambiado de estructura. Revisa el scraper.")
        if len(groups) == 0:
            sys.exit(1)

    scorers = parse_scorers(html)

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE_URL,
        "groups": groups,
    }
    if scorers:
        payload["scorers"] = scorers

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"OK: {OUTPUT_FILE} actualizado con {len(groups)} grupos.")


if __name__ == "__main__":
    main()
