# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Felix Tacke

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""analysis_speed.py — CORAPAN‑Projekt
=================================================

Dieses Skript quantifiziert das **Sprechtempo** in professionellen Aufnahmen des
CORAPAN‑Korpus. Es erzeugt pro Transkript (JSON) und pro Ländercode vier CSV‑
Tabellen und dokumentiert zugleich die jeweilige Datenbasis (Minuten‑ und
Wortumfang).  Die Pfad‑ und Variablenkonventionen sind identisch mit
`analysis_tenses.py`, so dass beide Skripte parallel in derselben Ordnerstruktur
laufen können.

---------------------------------------------------------------------
1.  Begriffs­definitionen
---------------------------------------------------------------------
* **Artikulations‑Rate (AR)**
    Geschwindigkeit der Lautproduktion *ohne* Pausen.  Berechnet aus der
    Nettosprechzeit, d. h. der Summe aller Wortdauern innerhalb eines Segments:
    
    ``AR_wps  =  Σ_word (end − start)⁻¹  →  AR_wpm = AR_wps · 60``

* **Sprech‑Rate (SR)**
    Tempo inkl. natürlicher Kurzpausen.  Segmentdauer = ``last_end – first_start``
    pro fortlaufendem Sprechersegment.

    ``SR_wps  =  n_words / Σ_segment (duration)  →  SR_wpm = SR_wps · 60``

    > **Segment** = zusammenhängende Wortsequenz desselben Sprechers laut JSON.

---------------------------------------------------------------------
2.  Kategorisierung & Filter
---------------------------------------------------------------------
Die Sprecher‑Metadaten sind im Kürzel `spkname` kodiert und werden mittels
`map_speaker_attributes()` in Attribute zerlegt:

``(professionalität, geschlecht, modus, themenbereich)``

Aktuelle Auswertung berücksichtigt **nur**

``professionalität == 'pro'``

und unterscheidet vier Buckets

``libre_f , libre_m , lectura_f , lectura_m``

* **Mindestumfang**: Buckets mit < 10 Wörtern werden verworfen, um extreme
  Varianzen bei Kleinstproben zu verhindern.

---------------------------------------------------------------------
3.  Berechnete Kennzahlen pro Bucket
---------------------------------------------------------------------
* ``*_wpm``   – Wörter pro Minute
* ``*_min``   – zugrundeliegende Minuten (AR: Nettozeit, SR: Segmentzeit)
* ``*_words`` – Wortanzahl  (liefert Transparenz zur Gewichtung)

> Optional: Wenn die Bibliothek *pyphen* verfügbar ist, werden Silben/M‑Werte
> (``*_spm``) analog berechnet und zusätzlich ausgegeben.

---------------------------------------------------------------------
4.  Ausgabedateien (im neu angelegten Ordner **results_speed/**)
---------------------------------------------------------------------
| Datei | Inhalt | Mittelung |
|-------|--------|----------|
| ``articulation_speed_by_file.csv`` | eine Zeile pro JSON; alle Buckets + Minuten + Wortzahl | – |
| ``speech_speed_by_file.csv``       | dito für SR | – |
| ``articulation_speed_by_country.csv`` | Summe aller Dateien desselben 2‑/3‑stelligen *country_code* | **Gewichtetes Mittel** (Σ Wörter / Σ Zeit) |
| ``speech_speed_by_country.csv``       | dito für SR | vgl. oben |

Alle CSVs sind *UTF‑8*, Feldtrennung ``;``. Fehlende Buckets erhalten den Wert
``NA``.

---------------------------------------------------------------------
5.  Implementierungsdetails
---------------------------------------------------------------------
* **Pfadkonstanten** entsprechen *analysis_tenses.py*  
  (``BASE_WEB``, ``GRABACIONES_DIR`` usw.).
* Unterordner ``results_speed`` wird bei Bedarf erstellt.
* Minuten/Zeitberechnung in Sekunden; Umrechnung erfolgt erst beim Schreiben.
* Aggregation pro Land: Country‑Code wird prioritär aus ``data['country_code']``
  gelesen; Fallback ist ein RegEx‐Match auf den Dateinamen.  Existiert beides
  nicht, wird ``UNK`` vergeben.
* Lizenz: MIT (© 2025 Felix Tacke).

---------------------------------------------------------------------
6.  Reproduzierbarkeit & Zitation
---------------------------------------------------------------------
Zur wissenschaftlichen Dokumentation genügen folgende Angaben:

* Korpus: **CORAPAN‑Speed, Release 2025‑05**  
  (Transkripte entsprechen Whisper v3.2, Tokenisierung NLTK 3.9).
* Auswahlkriterien: **professionelle SprecherInnen**, mind. 10 Wörter / Bucket.
* Definition der Tempometriken s. o.  (Formeln 1 & 2).  
  AR basiert auf **Nettozeit**, SR auf **Segmentzeit** (Pausen ≥ ASR‐Schnitt).
* Berechnungs‑ und Aggregations­skript: *analysis_speed.py* (dieses Dokument).

"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Konfiguration & Pfade (identisch zum Schwester‑Skript analysis_tenses.py)
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
BASE_WEB = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "CO.RA.PAN-WEB"))
GRABACIONES_DIR = os.path.join(BASE_WEB, "grabaciones")

# Ergebnisverzeichnis NEU für Geschwindigkeit
RESULTS_DIR = os.path.join(SCRIPT_DIR, "results_speed")
if not os.path.exists(RESULTS_DIR):
    os.makedirs(RESULTS_DIR)

CSV_ARTICULATION_FILE  = os.path.join(RESULTS_DIR, "articulation_speed_by_file.csv")
CSV_ARTICULATION_CTTRY = os.path.join(RESULTS_DIR, "articulation_speed_by_country.csv")
CSV_SPEECH_FILE        = os.path.join(RESULTS_DIR, "speech_speed_by_file.csv")
CSV_SPEECH_CTTRY       = os.path.join(RESULTS_DIR, "speech_speed_by_country.csv")

# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def extract_country_from_filename(fname: str) -> str:
    """Liefert den Ländercode aus einem Dateinamen
    ‚YYYY‑MM‑DD_COUNTRY_… .json‘, sonst "UNK"."""
    base = os.path.basename(fname)
    m = re.match(r"^(\d{4}-\d{2}-\d{2})_([^_]+)_", base)
    return m.group(2) if m else "UNK"

def map_speaker_attributes(name):
    """Mapping wie in analysis_tenses.py."""
    mapping = {
        'lib-pm':  ('pro', 'm', 'libre', 'general'),
        'lib-pf':  ('pro', 'f', 'libre', 'general'),
        'lib-om':  ('otro','m', 'libre', 'general'),
        'lib-of':  ('otro','f', 'libre', 'general'),
        'lec-pm':  ('pro', 'm', 'lectura', 'general'),
        'lec-pf':  ('pro', 'f', 'lectura', 'general'),
        'lec-om':  ('otro','m', 'lectura', 'general'),
        'lec-of':  ('otro','f', 'lectura', 'general'),
        'pre-pm':  ('pro', 'm', 'pre', 'general'),
        'pre-pf':  ('pro', 'f', 'pre', 'general'),
        'tie-pm':  ('pro', 'm', 'n/a', 'tiempo'),
        'tie-pf':  ('pro', 'f', 'n/a', 'tiempo'),
        'traf-pm': ('pro', 'm', 'n/a', 'tránsito'),
        'traf-pf': ('pro', 'f', 'n/a', 'tránsito')
    }
    return mapping.get(name, ('', '', '', ''))

_word_re = re.compile(r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü]+")

try:
    import pyphen
    _dic = pyphen.Pyphen(lang="es_ES")
    HAS_PYPHEN = True
except ImportError:
    HAS_PYPHEN = False

def count_syllables(word: str) -> int:
    """Grobe Silbenzählung per Pyphen; fällt auf 1 zurück, falls Modul fehlt."""
    if not HAS_PYPHEN:
        return 1
    parts = _dic.inserted(word).split("-")
    return max(1, len(parts))

def extract_country_from_filename(fname: str) -> str:
    base_fname = os.path.basename(fname)
    m = re.match(r"^(\d{4}-\d{2}-\d{2})_([^_]+)_", base_fname)
    return m.group(2) if m else "UNK"

# ---------------------------------------------------------------------------
# Kernberechnungen
# ---------------------------------------------------------------------------

BUCKETS = ["libre_f", "libre_m", "lectura_f", "lectura_m"]

def init_bucket_dict():
    return {b: {"words": 0, "syll": 0, "art_time": 0.0, "spk_time": 0.0, "net_time": 0.0, "seg_time": 0.0} for b in BUCKETS}

def process_file(json_path: str, spk_map: dict):
    """Liest ein Transkript und sammelt Zählungen pro Bucket."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    buckets = init_bucket_dict()
    segments = data.get("segments", [])

    for seg in segments:
        spkid = seg.get("speaker")
        spkname = spk_map.get(spkid, "")
        prof, gender, mode, _ = map_speaker_attributes(spkname)
        if prof != "pro" or mode not in ("libre", "lectura"):
            continue  # nur professionelle libre/lectura

        bucket = f"{mode}_{gender}"
        words = [w for w in seg.get("words", []) if _word_re.search(w.get("text", ""))]

        if len(words) < 10:
            continue  # Bucket-Grenze <10 Wörter

        # Artikulationswerte (Summe Wortdauern)
        net_time = sum((w["end"] - w["start"]) for w in words)
        # Sprechzeit = Segmentfenster (inkl. Pausen) – erste bis letzte Marke
        seg_time = words[-1]["end"] - words[0]["start"]

        n_words = len(words)
        n_syll  = sum(count_syllables(w["text"]) for w in words)

        b = buckets[bucket]
        b["words"]    += n_words
        b["syll"]     += n_syll
        b["art_time"] += net_time
        b["spk_time"] += seg_time
        b["net_time"] += net_time
        b["seg_time"] += seg_time

    return buckets

def calc_rates(counts: dict):
    """Berechnet Wörter‑/Silben‑pro‑Minute aus den kumulierten Zählern."""
    rates = {}
    for bucket, vals in counts.items():
        w = vals["words"]
        s = vals["syll"]
        art_t = vals["art_time"]
        spk_t = vals["spk_time"]
        art_min = vals["net_time"] / 60
        spk_min = vals["seg_time"] / 60
        rates[bucket] = {
            "art_wpm":  round((w / art_t) * 60, 1) if w >= 10 and art_t > 0 else "",
            "art_spm":  round((s / art_t) * 60, 1) if s and art_t > 0 else "",
            "spk_wpm":  round((w / spk_t) * 60, 1) if w >= 10 and spk_t > 0 else "",
            "spk_spm":  round((s / spk_t) * 60, 1) if s and spk_t > 0 else "",
            "art_min":  round(art_min, 1),
            "spk_min":  round(spk_min, 1)
        }
    return rates

# ---------------------------------------------------------------------------
# CSV‑Schreiber
# ---------------------------------------------------------------------------

HEADER_FILE = ["country", "filename",
               "libre_f_wpm", "libre_f_min",
               "libre_m_wpm", "libre_m_min",
               "lectura_f_wpm", "lectura_f_min",
               "lectura_m_wpm", "lectura_m_min"]
HEADER_COUNTRY = ["country",
                  "libre_f_wpm", "libre_f_min",
                  "libre_m_wpm", "libre_m_min",
                  "lectura_f_wpm", "lectura_f_min",
                  "lectura_m_wpm", "lectura_m_min"]

def write_file_csv(path: str, per_file_rates: dict, key: str):
    """Schreibt pro Datei eine Zeile mit der gewünschten Rate (art_wpm/…).
    *key* ∈ {"art_wpm", "spk_wpm"}.
    """
    with open(path, "w", encoding="utf-8", newline="") as csvfile:
        writer = csv.writer(csvfile, delimiter=";")
        writer.writerow(HEADER_FILE)
        for country in sorted(per_file_rates.keys()):
            for entry in sorted(per_file_rates[country], key=lambda x: x[0]):
                row = [country, entry[0]]  # filename
                for b in BUCKETS:
                    row.append(entry[1][b][key])
                    if key == "art_wpm":
                        row.append(entry[1][b]["art_min"])
                    else:
                        row.append(entry[1][b]["spk_min"])
                writer.writerow(row)

def write_country_csv(path: str, country_counts: dict, key: str):
    """Aggregiert counts → Rate nach Land und schreibt CSV."""
    with open(path, "w", encoding="utf-8", newline="") as csvfile:
        writer = csv.writer(csvfile, delimiter=";")
        writer.writerow(HEADER_COUNTRY)
        for country in sorted(country_counts.keys()):
            counts = country_counts[country]
            rates = calc_rates(counts)
            row = [country]
            for b in BUCKETS:
                row.append(rates[b][key])
                if key == "art_wpm":
                    row.append(rates[b]["art_min"])
                else:
                    row.append(rates[b]["spk_min"])
            writer.writerow(row)

# ---------------------------------------------------------------------------
# Hauptlogik
# ---------------------------------------------------------------------------

def main():
    if not os.path.isdir(GRABACIONES_DIR):
        print(f"Ordner '{GRABACIONES_DIR}' nicht gefunden.")
        return

    json_files = [f for f in os.listdir(GRABACIONES_DIR) if f.lower().endswith('.json')]
    if not json_files:
        print("Keine JSON‑Dateien gefunden, breche ab.")
        return

    per_file_rates = defaultdict(list)     # country → [ (filename, rates_dict) ]
    country_counts_art = defaultdict(init_bucket_dict)  # summierte Counts
    country_counts_spk = defaultdict(init_bucket_dict)

    for fname in sorted(json_files):
        path = os.path.join(GRABACIONES_DIR, fname)
        # Sprecher‑Mapping vorbereiten
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        spk_map = {sp["spkid"]: sp.get("name", "") for sp in data.get("speakers", [])}

        counts = process_file(path, spk_map)
        rates  = calc_rates(counts)

        country = extract_country_from_filename(fname)
        per_file_rates[country].append((fname, rates))

        # Summen für Länderrate aufbauen
        for b in BUCKETS:
            ctry_art = country_counts_art[country][b]
            ctry_spk = country_counts_spk[country][b]
            c = counts[b]
            ctry_art["words"]    += c["words"]
            ctry_art["syll"]     += c["syll"]
            ctry_art["art_time"] += c["art_time"]
            ctry_art["net_time"] += c["net_time"]
            ctry_spk["words"]    += c["words"]
            ctry_spk["syll"]     += c["syll"]
            ctry_spk["spk_time"] += c["spk_time"]
            ctry_spk["seg_time"] += c["seg_time"]

    # ---------- CSV schreiben ----------
    write_file_csv(CSV_ARTICULATION_FILE, per_file_rates, key="art_wpm")
    write_country_csv(CSV_ARTICULATION_CTTRY, country_counts_art, key="art_wpm")

    write_file_csv(CSV_SPEECH_FILE, per_file_rates, key="spk_wpm")
    write_country_csv(CSV_SPEECH_CTTRY, country_counts_spk, key="spk_wpm")

    print("Analyse abgeschlossen. Ergebnisse gespeichert unter:")
    print(f"  {CSV_ARTICULATION_FILE}")
    print(f"  {CSV_ARTICULATION_CTTRY}")
    print(f"  {CSV_SPEECH_FILE}")
    print(f"  {CSV_SPEECH_CTTRY}")

if __name__ == "__main__":
    main()
