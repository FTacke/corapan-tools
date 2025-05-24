#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
analysis_tenses.py

Dieses Skript analysiert alle annotierten JSON-Dateien im Ordner "grabaciones",
die mit spaCy und einem Post-Processing für Futur- und Pasado-Formen versehen sind.

Es werden sowohl Futurformen als auch Pasado-Formen ausgewertet:

Futurformen:
- analytisches Futur in Präsens (Future_Type = "analyticalFuture")
- analytisches Futur in Vergangenheit (Future_Type = "analyticalFuture_past", wird separat gezählt, aber nicht in Prozentrechnung einbezogen)
- synthetisches Futur (Tense im Morph-Objekt = "Fut")

Pasado-Formen:
- PerfectoCompuesto
- PerfectoSimple

Die Auswertung erfolgt differenziert nach Sprechmodus:
- habla_libre (lib-pm, lib-pf)
- lectura (lec-pm, lec-pf)
- pregrabado (pre-pm, pre-pf)

Für jede Datei und jeden Modus werden absolute Häufigkeiten und prozentuale Anteile berechnet.
Die Ergebnisse werden in separaten CSV-Dateien gespeichert, getrennt für Futur und Pasado:
- analysis_future_results_total.csv
- analysis_future_results_libre.csv
- analysis_future_results_lectura.csv
- analysis_future_results_pre.csv
- analysis_pasado_results_total.csv
- analysis_pasado_results_libre.csv
- analysis_pasado_results_lectura.csv
- analysis_pasado_results_pre.csv
"""

import os
import re
import csv
import json
from collections import defaultdict

# Das Mapping der Sprecherattribute wird hier direkt definiert, basierend auf database_creation.py
def map_speaker_attributes(name):
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
    return mapping.get(name, ('','', '',''))

# Ordner, in dem sich dieses Skript befindet
SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
BASE_WEB = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "CO.RA.PAN-WEB"))
GRABACIONES_DIR = os.path.join(BASE_WEB, "grabaciones")

# Ordner für Ergebnis-CSV-Dateien (neu)
RESULTS_DIR = os.path.join(SCRIPT_DIR, "results")

# Dateinamen für die Ergebnis-CSV-Dateien
RESULTS_CSV_FUTURE_TOTAL = os.path.join(RESULTS_DIR, "analysis_future_results_total.csv")
RESULTS_CSV_FUTURE_LIBRE = os.path.join(RESULTS_DIR, "analysis_future_results_libre.csv")
RESULTS_CSV_FUTURE_LECTURA = os.path.join(RESULTS_DIR, "analysis_future_results_lectura.csv")
RESULTS_CSV_FUTURE_PRE = os.path.join(RESULTS_DIR, "analysis_future_results_pre.csv")

RESULTS_CSV_PASADO_TOTAL = os.path.join(RESULTS_DIR, "analysis_pasado_results_total.csv")
RESULTS_CSV_PASADO_LIBRE = os.path.join(RESULTS_DIR, "analysis_pasado_results_libre.csv")
RESULTS_CSV_PASADO_LECTURA = os.path.join(RESULTS_DIR, "analysis_pasado_results_lectura.csv")
RESULTS_CSV_PASADO_PRE = os.path.join(RESULTS_DIR, "analysis_pasado_results_pre.csv")

def extract_country_from_filename(fname: str) -> str:
    base_fname = os.path.basename(fname)
    m = re.match(r"^(\d{4}-\d{2}-\d{2})_([^_]+)_", base_fname)
    return m.group(2) if m else "UNK"

def initialize_counters():
    return {
        'analyticalFuture': 0,
        'simpleFuture': 0,
        'compoundPast': 0,
        'simplePast': 0
    }

def update_future_counters(counters, future_type, tense_vals):
    if future_type == 'analyticalFuture':
        counters['analyticalFuture'] += 1
    elif 'Fut' in tense_vals:
        counters['simpleFuture'] += 1

def update_pasado_counters(counters, morph):
    if not isinstance(morph, dict):
        return
    if "Past" in morph.get("Tense", []):
        ptype = morph.get("Past_Tense_Type", "PastOther")
        if ptype == "PerfectoCompuesto":
            counters['compoundPast'] += 1
        elif ptype == "PerfectoSimple":
            counters['simplePast'] += 1

def write_results_csv(path, results, is_future=True):
    with open(path, "w", encoding="utf-8", newline="") as csvfile:
        writer = csv.writer(csvfile, delimiter=";")
        if is_future:
            header = [
                "country",
                "filename",
                "analyticalFuture",
                "simpleFuture",
                "TotalFuture",
                "% analyticalFuture",
                "% simpleFuture",
            ]
        else:
            header = [
                "country",
                "filename",
                "compoundPast",
                "simplePast",
                "TotalPast",
                "% compoundPast",
                "% simplePast",
            ]
        writer.writerow(header)
        for country in sorted(results.keys()):
            entries = sorted(results[country], key=lambda x: x[0])
            sum_af = 0
            sum_fut = 0
            sum_pc = 0
            sum_ps = 0
            for entry in entries:
                fname = entry[0]
                if is_future:
                    af, fut, total = entry[1], entry[2], entry[3]
                    if total > 0:
                        perc_af = round((af / total) * 100, 1)
                        perc_fut = round((fut / total) * 100, 1)
                    else:
                        perc_af = perc_fut = 0.0
                    writer.writerow(
                        [country, fname, af, fut, total, perc_af, perc_fut]
                    )
                    sum_af += af
                    sum_fut += fut
                else:
                    pc, ps, total = entry[1], entry[2], entry[3]
                    if total > 0:
                        perc_pc = round((pc / total) * 100, 1)
                        perc_ps = round((ps / total) * 100, 1)
                    else:
                        perc_pc = perc_ps = 0.0
                    writer.writerow(
                        [country, fname, pc, ps, total, perc_pc, perc_ps]
                    )
                    sum_pc += pc
                    sum_ps += ps
            group_total = sum_af + sum_fut if is_future else sum_pc + sum_ps
            if group_total > 0:
                group_perc_af = round((sum_af / group_total) * 100, 1)
                group_perc_fut = round((sum_fut / group_total) * 100, 1)
                group_perc_pc = round((sum_pc / group_total) * 100, 1)
                group_perc_ps = round((sum_ps / group_total) * 100, 1)
            else:
                group_perc_af = group_perc_fut = group_perc_pc = group_perc_ps = 0.0
            if is_future:
                writer.writerow(
                    [country, f"SUM {country}", sum_af, sum_fut, group_total, group_perc_af, group_perc_fut]
                )
            else:
                writer.writerow(
                    [country, f"SUM {country}", sum_pc, sum_ps, group_total, group_perc_pc, group_perc_ps]
                )
            writer.writerow([])

def main():
    if not os.path.isdir(GRABACIONES_DIR):
        print(f"Ordner '{GRABACIONES_DIR}' nicht gefunden.")
        return

    # Ordner für Ergebnisse erstellen, falls nicht vorhanden
    if not os.path.exists(RESULTS_DIR):
        os.makedirs(RESULTS_DIR)

    json_files = [f for f in os.listdir(GRABACIONES_DIR) if f.lower().endswith('.json')]
    if not json_files:
        print("Keine JSON-Dateien gefunden, breche ab.")
        return

    # Ergebnisse für alle Modi initialisieren
    results_future_total = defaultdict(list)
    results_future_libre = defaultdict(list)
    results_future_lectura = defaultdict(list)
    results_future_pre = defaultdict(list)

    results_pasado_total = defaultdict(list)
    results_pasado_libre = defaultdict(list)
    results_pasado_lectura = defaultdict(list)
    results_pasado_pre = defaultdict(list)

    for filename in sorted(json_files):
        file_path = os.path.join(GRABACIONES_DIR, filename)
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Sprecher-Mapping aus JSON
        spk_map = {}
        for sp in data.get('speakers', []):
            sid = sp.get('spkid')
            sname = sp.get('name')
            if sid:
                spk_map[sid] = sname

        # Zähler für alle Modi initialisieren
        counters_future_total = initialize_counters()
        counters_future_libre = initialize_counters()
        counters_future_lectura = initialize_counters()
        counters_future_pre = initialize_counters()

        counters_pasado_total = initialize_counters()
        counters_pasado_libre = initialize_counters()
        counters_pasado_lectura = initialize_counters()
        counters_pasado_pre = initialize_counters()

        segments = data.get('segments', [])
        for seg in segments:
            spkid = seg.get('speaker')
            spkname = spk_map.get(spkid, '')
            _, _, mode, _ = map_speaker_attributes(spkname)

            wlist = seg.get('words', [])
            for w_obj in wlist:
                morph = w_obj.get('morph', {})
                if not isinstance(morph, dict):
                    continue

                # Futur-Formen zählen
                future_type = morph.get('Future_Type', '')
                tense_vals = morph.get('Tense', [])
                update_future_counters(counters_future_total, future_type, tense_vals)
                if mode == 'libre':
                    update_future_counters(counters_future_libre, future_type, tense_vals)
                elif mode == 'lectura':
                    update_future_counters(counters_future_lectura, future_type, tense_vals)
                elif mode == 'pre':
                    update_future_counters(counters_future_pre, future_type, tense_vals)

                # Pasado-Formen zählen
                update_pasado_counters(counters_pasado_total, morph)
                if mode == 'libre':
                    update_pasado_counters(counters_pasado_libre, morph)
                elif mode == 'lectura':
                    update_pasado_counters(counters_pasado_lectura, morph)
                elif mode == 'pre':
                    update_pasado_counters(counters_pasado_pre, morph)

        total_for_percentage_future_total = counters_future_total['analyticalFuture'] + counters_future_total['simpleFuture']
        total_for_percentage_future_libre = counters_future_libre['analyticalFuture'] + counters_future_libre['simpleFuture']
        total_for_percentage_future_lectura = counters_future_lectura['analyticalFuture'] + counters_future_lectura['simpleFuture']
        total_for_percentage_future_pre = counters_future_pre['analyticalFuture'] + counters_future_pre['simpleFuture']

        total_for_percentage_pasado_total = counters_pasado_total['compoundPast'] + counters_pasado_total['simplePast']
        total_for_percentage_pasado_libre = counters_pasado_libre['compoundPast'] + counters_pasado_libre['simplePast']
        total_for_percentage_pasado_lectura = counters_pasado_lectura['compoundPast'] + counters_pasado_lectura['simplePast']
        total_for_percentage_pasado_pre = counters_pasado_pre['compoundPast'] + counters_pasado_pre['simplePast']

        country_code = extract_country_from_filename(filename)

        # Ergebnisse speichern
        results_future_total[country_code].append([
            filename,
            counters_future_total['analyticalFuture'],
            counters_future_total['simpleFuture'],
            total_for_percentage_future_total
        ])
        results_future_libre[country_code].append([
            filename,
            counters_future_libre['analyticalFuture'],
            counters_future_libre['simpleFuture'],
            total_for_percentage_future_libre
        ])
        results_future_lectura[country_code].append([
            filename,
            counters_future_lectura['analyticalFuture'],
            counters_future_lectura['simpleFuture'],
            total_for_percentage_future_lectura
        ])
        results_future_pre[country_code].append([
            filename,
            counters_future_pre['analyticalFuture'],
            counters_future_pre['simpleFuture'],
            total_for_percentage_future_pre
        ])

        results_pasado_total[country_code].append([
            filename,
            counters_pasado_total['compoundPast'],
            counters_pasado_total['simplePast'],
            total_for_percentage_pasado_total
        ])
        results_pasado_libre[country_code].append([
            filename,
            counters_pasado_libre['compoundPast'],
            counters_pasado_libre['simplePast'],
            total_for_percentage_pasado_libre
        ])
        results_pasado_lectura[country_code].append([
            filename,
            counters_pasado_lectura['compoundPast'],
            counters_pasado_lectura['simplePast'],
            total_for_percentage_pasado_lectura
        ])
        results_pasado_pre[country_code].append([
            filename,
            counters_pasado_pre['compoundPast'],
            counters_pasado_pre['simplePast'],
            total_for_percentage_pasado_pre
        ])

    # CSV-Dateien schreiben
    write_results_csv(RESULTS_CSV_FUTURE_TOTAL, results_future_total, is_future=True)
    write_results_csv(RESULTS_CSV_FUTURE_LIBRE, results_future_libre, is_future=True)
    write_results_csv(RESULTS_CSV_FUTURE_LECTURA, results_future_lectura, is_future=True)
    write_results_csv(RESULTS_CSV_FUTURE_PRE, results_future_pre, is_future=True)

    write_results_csv(RESULTS_CSV_PASADO_TOTAL, results_pasado_total, is_future=False)
    write_results_csv(RESULTS_CSV_PASADO_LIBRE, results_pasado_libre, is_future=False)
    write_results_csv(RESULTS_CSV_PASADO_LECTURA, results_pasado_lectura, is_future=False)
    write_results_csv(RESULTS_CSV_PASADO_PRE, results_pasado_pre, is_future=False)

    print("Analyse abgeschlossen. Ergebnisse in den CSV-Dateien gespeichert.")

if __name__ == "__main__":
    main()
