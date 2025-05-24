#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
database_creation.py

Erstellt und aktualisiert mehrere SQLite-Datenbanken aus allen JSON-Dateien im Ordner "grabaciones":
  1) db_public/stats_all.db    -> Gesamtzahl Wörter & Gesamtdauer
  2) db/stats_country.db       -> Wortzahl & Dauer pro Land (Spalte 'country')
  3) db/stats_files.db         -> Metadaten pro Datei (Spalte 'country')
  4) db/transcription.db       -> Tabelle tokens mit 'lemma'
  5) db/annotation_data.db     -> Tabelle annotations mit 'foreign_word'
"""

import os
import json
import sqlite3
import hashlib
import string
from collections import OrderedDict

# ----------------------------------------------------------------------
# Hilfsfunktionen
# ----------------------------------------------------------------------
def seconds_to_hms(seconds):
    hrs, r = divmod(seconds, 3600)
    mins, secs = divmod(r, 60)
    return f"{int(hrs):02d}:{int(mins):02d}:{int(secs):02d}"

def seconds_to_hms_files(seconds):
    hrs, r = divmod(seconds, 3600)
    mins, secs = divmod(r, 60)
    return f"{int(hrs):02d}:{int(mins):02d}:{secs:.2f}"

def is_sentence_boundary(word_text):
    """Prüft, ob ein Wort mit Satzschlusszeichen (., !, ?) endet."""
    if not word_text:
        return False
    return word_text[-1] in ['.', '!', '?']

def map_speaker_attributes(name):
    """Ordnet einem Sprechername (z.B. 'traf-pf') ein Tupel (speaker_type, sex, mode) zu."""
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

def get_left_with_sentence_bounds(words, center_index, max_count=10):
    """
    Nimmt bis zu max_count Tokens links, stoppt jedoch an Satzgrenze (., !, ?).
    Die satzabschließende Token wird nicht mehr in den linken Kontext aufgenommen.
    """
    result = []
    steps = 0
    idx = center_index - 1
    while idx >= 0 and steps < max_count:
        if is_sentence_boundary(words[idx].get('text','')):
            break
        result.append(words[idx])
        steps += 1
        idx -= 1
    result.reverse()
    return result

def get_right_with_sentence_bounds(words, center_index, max_count=10):
    """
    Nimmt bis zu max_count Tokens rechts, stoppt nach dem ersten Token, das Satzende ist (oder einschließt).
    NEU: Wenn das aktuelle Token selbst (center_index) ein Satzende hat, gibt es gar keinen rechten Kontext.
    """
    if is_sentence_boundary(words[center_index].get('text','')):
        return []

    result = []
    steps = 0
    idx = center_index + 1
    while idx < len(words) and steps < max_count:
        w_text = words[idx].get('text','')
        result.append(words[idx])
        steps += 1
        if is_sentence_boundary(w_text):
            break
        idx += 1
    return result

def build_string_context(word_list):
    return ' '.join(w.get('text','') for w in word_list)

# Adaptive Token-ID-Funktion: Zunächst 5 Hash-Zeichen; bei Kollision sukzessive verlängern.
def generate_unique_token_id(country_code, date, st, et, text, existing_ids):
    text_part = text[:3] if len(text) >= 3 else text
    composite = f"{date}_{st}_{et}_{text_part}"
    hash_full = hashlib.md5(composite.encode('utf-8')).hexdigest()
    hash_len = 5
    token_id = f"{country_code}{hash_full[:hash_len]}"
    extension_count = 0
    while token_id in existing_ids:
        hash_len += 1
        extension_count += 1
        token_id = f"{country_code}{hash_full[:hash_len]}"
    existing_ids.add(token_id)
    return token_id, extension_count

def insert_token_id_after_text(word, token_id):
    new_word = OrderedDict()
    inserted = False
    for key, value in word.items():
        new_word[key] = value
        if key == "text" and not inserted:
            new_word["token_id"] = token_id
            inserted = True
    if not inserted:
        new_word["token_id"] = token_id
    return new_word


# ----------------------------------------------------------------------
# Verzeichnisse
# ----------------------------------------------------------------------

SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
BASE_WEB = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "CO.RA.PAN-WEB"))
DB_DIR = os.path.join(BASE_WEB, "db")
DB_PUBLIC_DIR = os.path.join(BASE_WEB, "db_public")
GRABACIONES_DIR = os.path.join(BASE_WEB, "grabaciones")

# ----------------------------------------------------------------------
# 1) stats_all.db
# ----------------------------------------------------------------------
def run_stats_all():
    os.makedirs(DB_PUBLIC_DIR, exist_ok=True)
    db_path = os.path.join(DB_PUBLIC_DIR, 'stats_all.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS stats (
            id INTEGER PRIMARY KEY,
            total_word_count INTEGER,
            total_duration_all TEXT
        )
    ''')

    folder = GRABACIONES_DIR
    json_files = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith('.json')]

    total_word_count = 0
    max_end_times = []

    for jf in json_files:
        with open(jf, 'r', encoding='utf-8-sig') as file:
            data = json.load(file)
            max_end_time = 0.0
            for seg in data.get('segments', []):
                wds = seg.get('words', [])
                total_word_count += len(wds)
                if wds:
                    e = wds[-1].get('end', 0.0)
                    if e > max_end_time:
                        max_end_time = e
            max_end_times.append(max_end_time)

    total_dur = seconds_to_hms(sum(max_end_times))

    c.execute("SELECT id FROM stats WHERE id=1")
    row_exists = c.fetchone()
    if row_exists:
        c.execute(
            "UPDATE stats SET total_word_count=?, total_duration_all=? WHERE id=1",
            (total_word_count, total_dur)
        )
        if c.rowcount > 0:
            print(f"1/4 --> stats_all.db: Datensatz aktualisiert (Wörter={total_word_count}, Dauer={total_dur}).")
        else:
            print("1/4 --> stats_all.db: Keine Änderung nötig (war bereits aktuell).")
    else:
        c.execute(
            "INSERT INTO stats (id, total_word_count, total_duration_all) VALUES (1, ?, ?)",
            (total_word_count, total_dur)
        )
        print(f"1/4 --> stats_all.db: Neuer Datensatz eingefügt (Wörter={total_word_count}, Dauer={total_dur}).")

    conn.commit()
    conn.close()

# ----------------------------------------------------------------------
# 2) stats_country.db
# ----------------------------------------------------------------------
def run_stats_country():
    os.makedirs(DB_DIR, exist_ok=True)           
    db_path = os.path.join(DB_DIR, 'stats_country.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("DROP TABLE IF EXISTS stats_country")
    c.execute('''
        CREATE TABLE stats_country (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            country TEXT UNIQUE,
            total_word_count INTEGER,
            total_duration_country TEXT
        )
    ''')

    folder = GRABACIONES_DIR
    json_files = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith('.json')]

    cdict = {}  # country -> [acc_words, acc_time]

    for jf in json_files:
        with open(jf, 'r', encoding='utf-8-sig') as file:
            data = json.load(file)
            country_val = data.get("country", "")
            if not country_val:
                country_val = "UNK"

            total_w = 0
            max_end_time = 0.0
            for seg in data.get('segments', []):
                wds = seg.get('words', [])
                total_w += len(wds)
                if wds:
                    e = wds[-1].get('end', 0.0)
                    if e > max_end_time:
                        max_end_time = e

            if country_val not in cdict:
                cdict[country_val] = [0, 0.0]
            cdict[country_val][0] += total_w
            cdict[country_val][1] += max_end_time

    inserted_count = 0
    for country_key, (wc, total_end) in cdict.items():
        dur_str = seconds_to_hms(total_end)
        c.execute('''
            INSERT INTO stats_country (country, total_word_count, total_duration_country)
            VALUES (?, ?, ?)
        ''', (country_key, wc, dur_str))
        inserted_count += 1

    conn.commit()
    conn.close()
    print(f"2/4 --> stats_country.db: Neu erstellt. {inserted_count} Einträge eingefügt.")

# ----------------------------------------------------------------------
# 3) stats_files.db
# ----------------------------------------------------------------------
def run_stats_files():
    os.makedirs(DB_DIR, exist_ok=True)
    db_path = os.path.join(DB_DIR, 'stats_files.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE,
            country TEXT,
            radio TEXT,
            date TEXT,
            revision TEXT,
            word_count INTEGER,
            duration TEXT
        )
    ''')

    folder = GRABACIONES_DIR
    json_files = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith('.json')]

    updated_count = 0
    inserted_count = 0

    for jf in json_files:
        basef = os.path.basename(jf)
        with open(jf, 'r', encoding='utf-8-sig') as file:
            data = json.load(file)
            country = data.get('country','')
            radio = data.get('radio','')
            date = data.get('date','')
            revision = data.get('revision','')

            segs = data.get('segments', [])
            wc = sum(len(s.get('words', [])) for s in segs)
            last_end = 0.0
            for seg in segs:
                wds = seg.get('words', [])
                if wds:
                    e = wds[-1].get('end',0.0)
                    if e>last_end:
                        last_end = e
            dur_str = seconds_to_hms_files(last_end)

            c.execute("SELECT id FROM metadata WHERE filename=?", (basef,))
            row = c.fetchone()
            if row:
                c.execute('''
                    UPDATE metadata
                    SET country=?, radio=?, date=?, revision=?, word_count=?, duration=?
                    WHERE filename=?
                ''', (country, radio, date, revision, wc, dur_str, basef))
                if c.rowcount > 0:
                    updated_count += 1
            else:
                c.execute('''
                    INSERT INTO metadata (filename, country, radio, date, revision, word_count, duration)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (basef, country, radio, date, revision, wc, dur_str))
                if c.rowcount > 0:
                    inserted_count += 1

    conn.commit()
    conn.close()

    if updated_count == 0 and inserted_count == 0:
        print("3/4 --> stats_files.db: Keine Aktualisierung nötig (war bereits aktuell).")
    else:
        print(f"3/4 --> stats_files.db: {updated_count} Einträge aktualisiert, {inserted_count} neu eingefügt.")

# ----------------------------------------------------------------------
# 4) transcription.db: Neue Spalte lemma in tokens
#    annotation_data.db: Neue Spalte foreign_word in annotations
# ----------------------------------------------------------------------
def run_transcription():
    os.makedirs(DB_DIR, exist_ok=True)
    
    transcription_db_path = os.path.join(DB_DIR, 'transcription.db')
    annotation_db_path   = os.path.join(DB_DIR, 'annotation_data.db')
    
    # ---- transcription.db ----
    conn_trans = sqlite3.connect(transcription_db_path)
    c_trans = conn_trans.cursor()
    c_trans.execute("DROP TABLE IF EXISTS tokens")
    c_trans.execute('''
        CREATE TABLE tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_id TEXT UNIQUE,
            filename TEXT,
            country_code TEXT,
            radio TEXT,
            date TEXT,
            speaker_type TEXT,
            sex TEXT,
            mode TEXT,
            discourse TEXT,               -- Neu hinzugefügte Spalte
            text TEXT,
            start REAL,
            end REAL,
            context_left TEXT,
            context_right TEXT,
            context_start REAL,
            context_end REAL,
            lemma TEXT
        )
    ''')
    c_trans.execute("CREATE INDEX idx_tokens_token_id ON tokens(token_id)")
    
    # ---- annotation_data.db ----
    conn_ann = sqlite3.connect(annotation_db_path)
    c_ann = conn_ann.cursor()
    c_ann.execute("DROP TABLE IF EXISTS annotations")
    c_ann.execute('''
        CREATE TABLE annotations (
            token_id TEXT UNIQUE,
            segment_index INTEGER,
            token_index INTEGER,
            lemma TEXT,
            pos TEXT,
            dep TEXT,
            head_text TEXT,
            morph TEXT,
            neighbors_left TEXT,
            neighbors_right TEXT,
            foreign_word TEXT       -- Neu für Fremdwörter: "1" oder "0"
        )
    ''')
    c_ann.execute("CREATE INDEX idx_annotations_token_id ON annotations(token_id)")
    
    folder = GRABACIONES_DIR
    json_files = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith('.json')]
    inserted = 0
    empty_tokens_count = 0
    total_extensions = 0
    
    existing_ids = set()
    ignored_tokens = {"(", ")", "[", "]", "!", "(..)", "(.)", "(..", "(..).", "(..),", ").", ")]", ",", "."}
    
    for jf in json_files:
        basef = os.path.basename(jf)
        with open(jf, 'r', encoding='utf-8-sig') as file:
            data = json.load(file)
        json_modified = False
        real_fname = data.get('filename', basef)
        code_val = data.get("country_code", "UNK")
        radio = data.get('radio','')
        date = data.get('date','')
        
        # Sprecher-Mapping
        spk_map = {}
        for sp in data.get('speakers', []):
            sid = sp.get('spkid')
            sname = sp.get('name')
            if sid:
                spk_map[sid] = sname
        
        segments = data.get('segments', [])
        for seg_i, seg in enumerate(segments):
            spkid = seg.get('speaker')
            spkname = spk_map.get(spkid, '')
            speaker_type, sex, mode, discourse = map_speaker_attributes(spkname)
            
            wlist = seg.get('words', [])
            for i, w_obj in enumerate(wlist):
                txt = w_obj.get('text','').strip()
                if txt in ignored_tokens or (txt and all(ch in string.punctuation for ch in txt)):
                    empty_tokens_count += 1
                    continue
                
                # Lemma, POS etc. aus dem JSON
                lem = w_obj.get('lemma','')
                pos = w_obj.get('pos','')
                dep = w_obj.get('dep','')
                head = w_obj.get('head_text','')
                morph_json = json.dumps(w_obj.get('morph', {}), ensure_ascii=False)
                
                # Fremdwörterkennzeichnung aus JSON, Standardwert "0"
                foreign_val = w_obj.get('foreign', '0')
                
                st = w_obj.get('start', 0.0)
                et = w_obj.get('end', 0.0)
                
                left_tokens = get_left_with_sentence_bounds(wlist, i, max_count=10)
                right_tokens = get_right_with_sentence_bounds(wlist, i, max_count=10)
                
                nb_left = [{
                    "text": lw.get('text',''),
                    "lemma": lw.get('lemma',''),
                    "pos": lw.get('pos',''),
                    "dep": lw.get('dep',''),
                    "start": lw.get('start',0.0),
                    "end": lw.get('end',0.0)
                } for lw in left_tokens]
                
                nb_right = [{
                    "text": rw.get('text',''),
                    "lemma": rw.get('lemma',''),
                    "pos": rw.get('pos',''),
                    "dep": rw.get('dep',''),
                    "start": rw.get('start',0.0),
                    "end": rw.get('end',0.0)
                } for rw in right_tokens]
                
                nb_left_str = json.dumps(nb_left, ensure_ascii=False)
                nb_right_str = json.dumps(nb_right, ensure_ascii=False)
                
                ctx_left_str = build_string_context(left_tokens)
                ctx_right_str = build_string_context(right_tokens)
                
                if left_tokens:
                    ctx_start = max(0, left_tokens[0].get('start', st) - 0.25)
                else:
                    ctx_start = max(0, st - 0.25)
                if right_tokens:
                    ctx_end = right_tokens[-1].get('end', et) + 0.25
                else:
                    ctx_end = et + 0.25
                
                # Unique token_id
                token_id, ext = generate_unique_token_id(code_val, date, st, et, txt, existing_ids)
                total_extensions += ext
                
                # JSON updaten, falls token_id noch nicht da
                if "token_id" not in w_obj:
                    new_w_obj = insert_token_id_after_text(w_obj, token_id)
                    wlist[i] = new_w_obj
                    json_modified = True
                
                # transcription.db
                c_trans.execute('''
                    INSERT OR REPLACE INTO tokens (
                        token_id, filename, country_code, radio, date,
                        speaker_type, sex, mode, discourse,
                        text, start, end,
                        context_left, context_right,
                        context_start, context_end,
                        lemma
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    token_id, real_fname, code_val, radio, date,
                    speaker_type, sex, mode, discourse,
                    txt, st, et,
                    ctx_left_str, ctx_right_str,
                    ctx_start, ctx_end,
                    lem
                ))
                
                # annotation_data.db
                c_ann.execute('''
                    INSERT OR REPLACE INTO annotations (
                        token_id, segment_index, token_index,
                        lemma, pos, dep, head_text, morph,
                        neighbors_left, neighbors_right,
                        foreign_word
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    token_id, seg_i, i,
                    lem, pos, dep, head, morph_json,
                    nb_left_str, nb_right_str,
                    foreign_val   # "1" wenn w_obj["foreign"] vorhanden war, sonst "0"
                ))
                
                inserted += 1
        
        # JSON bei Bedarf überschreiben
        if json_modified:
            with open(jf, 'w', encoding='utf-8') as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
    
    conn_trans.commit()
    conn_ann.commit()
    conn_trans.close()
    conn_ann.close()
    total_processed = inserted + empty_tokens_count
    print(f"4/4 --> transcription.db & annotation_data.db: {inserted} Token-Zeilen geschrieben.")
    print(f"    --> IDs verlängert: {total_extensions}")
    print(f"    --> Empty Tokens ignoriert: {empty_tokens_count}")
    print(f"    --> Insgesamt verarbeitete Token: {total_processed}")

# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------
def main():
    run_stats_all()
    run_stats_country()
    run_stats_files()
    run_transcription()

if __name__ == "__main__":
    main()
