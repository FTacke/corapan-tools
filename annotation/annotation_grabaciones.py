# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Felix Tacke

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
annotation_grabaciones.py

Annotiert alle JSON-Dateien im Ordner "grabaciones" (relativ zwei Ebenen über diesem Skript).
Dabei werden in jedem Sprechersegment die Wörter nach Sätzen aufgeteilt.
Für jeden Satz wird spaCy mit Satz-1, Satz, Satz+1 als gemeinsamem Kontext aufgerufen,
um ggf. unvollständige Satzfragmente besser zu erfassen.

Nach der Annotation (Wörtern werden Felder wie pos, lemma, morph usw. hinzugefügt)
folgt ein Post-Processing, um spanische Vergangenheitsformen (PerfectoSimple,
PerfectoCompuesto usw.) sowie analytische Futurformen genauer zu klassifizieren.
Bereits annotierte Dateien (sofern ein Wort bereits pos/morph trägt) werden übersprungen.

Fortschrittsmeldungen:
- Zu Beginn: Anzahl zu annotierender Dateien & Gesamtzahl Wörter
- Beim Start jeder Datei: Meldung mit der Wortanzahl dieser Datei
- Alle 2500 Wörter (oder wenn Datei fertig): Fortschrittsmeldung
- Nach jeder Datei: prozentualer Gesamter Fortschritt
"""

import os
import json
import spacy
import warnings
import string

warnings.filterwarnings("ignore", category=FutureWarning)

# -----------------------------------------------------------------------------
# Ordnerpfade - wir gehen 2 Ebenen hoch (aus 'annotation' -> 'LOKAL' -> 'root')
# -----------------------------------------------------------------------------
SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
BASE_WEB = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "CO.RA.PAN-WEB"))
GRABACIONES_DIR = os.path.join(BASE_WEB, "grabaciones")

# Lade das gewünschte spaCy-Modell (z.B. "es_dep_news_trf" oder "es_core_news_md")
nlp = spacy.load("es_dep_news_trf")

# -----------------------------------------------------------------------------
# Hilfsfunktionen
# -----------------------------------------------------------------------------

def split_into_sentences(words_list):
    """
    Teilt das Wort-Array in 'Sätze' auf, anhand einfacher Satzzeichentrenner (. ? !).
    Gibt eine Liste von Sätzen zurück, wobei jeder Satz eine Liste von Wort-Objekten ist.
    """
    sentence_ends = {".", "?", "!"}
    sentences = []
    current_sentence = []

    for w in words_list:
        current_sentence.append(w)
        txt = w.get("text", "").strip().lower()
        if txt and any(txt.endswith(se) for se in sentence_ends):
            sentences.append(current_sentence)
            current_sentence = []

    # Falls letzter Satz nicht abgeschlossen war
    if current_sentence:
        sentences.append(current_sentence)

    return sentences


PUNCT_CHARS = string.punctuation + "¿¡"

def strip_punct(token_text: str) -> str:
    """
    Entfernt Satzzeichen am Wortanfang und -ende,
    inklusive umgekehrter ¿ ¡.
    """
    return token_text.strip(PUNCT_CHARS)


def annotate_fallback(word_text: str) -> dict:
    """
    Fallback: Einzelnes Wort separat parsen, falls kein direkter spaCy-Token passt.
    """
    doc = nlp(word_text)
    if len(doc) > 0:
        t = doc[0]
        return {
            "pos": t.pos_,
            "lemma": t.lemma_,
            "dep": t.dep_,
            "head_text": t.head.text if t.head else "",
            "morph": t.morph.to_dict()
        }
    else:
        return {
            "pos": "",
            "lemma": word_text,
            "dep": "",
            "head_text": "",
            "morph": {}
        }


def fill_word_annotation(w_obj, spacy_token):
    """
    Überträgt POS, Lemma, Dep, Morph eines spaCy-Token auf das Wort-Objekt.
    """
    w_obj["pos"] = spacy_token.pos_
    w_obj["lemma"] = spacy_token.lemma_
    w_obj["dep"] = spacy_token.dep_
    w_obj["head_text"] = spacy_token.head.text if spacy_token.head else ""
    w_obj["morph"] = spacy_token.morph.to_dict()


def already_annotated(segments) -> bool:
    """
    Prüft, ob in den gegebenen Segmenten schon mind. ein Wort mit "pos" oder "morph" existiert.
    Falls ja => Datei ist bereits annotiert.
    """
    for seg in segments:
        for w in seg.get("words", []):
            if "pos" in w or "morph" in w:
                return True
    return False

# -----------------------------------------------------------------------------
# Fortschrittsmeldungen
# -----------------------------------------------------------------------------

def show_progress(progress_data):
    """
    Gibt alle 2500 Wörter oder am Ende der Datei eine Meldung aus,
    wie viele Wörter bisher annotiert sind.
    """
    annotated = progress_data["annotated"]
    total = progress_data["total"]
    current_step = annotated // 2500
    if current_step > progress_data["last_step"] or annotated == total:
        progress_data["last_step"] = current_step
        print(f"      Zwischenschritt: {annotated} / {total} Wörter annotiert.")


def file_finished_message(progress_data):
    """
    Meldung nach jeder Datei, wieviel Prozent aller Wörter fertig sind.
    """
    annotated = progress_data["annotated"]
    total = progress_data["total"]
    pct = 100.0 * annotated / total
    print(f"      -> Aktuell: {annotated} von {total} Wörtern ({pct:.1f}%).")

# -----------------------------------------------------------------------------
# Post-Processing (Vergangenheitsformen)
# -----------------------------------------------------------------------------
PRESENT_FORMS = {
    "he", "has", "ha", "hemos", "habéis", "han", "habés", "habís", "habemos"
}
IMPERFECT_FORMS = {"había", "habías", "habíamos", "habíais", "habían"}
FUTURE_FORMS    = {"habré", "habrás", "habrá", "habremos", "habréis", "habrán"}
COND_FORMS      = {"habría", "habrías", "habríamos", "habríais", "habrían"}


def set_past_tense_type(w_obj: dict, label: str):
    """
    Setzt ein benutzerdefiniertes Feld 'Past_Tense_Type' im Morph-Objekt.
    """
    if not isinstance(w_obj.get("morph"), dict):
        w_obj["morph"] = {}
    w_obj["morph"]["Past_Tense_Type"] = label


def detect_compound_any_fallback(part_word: dict, seg_words: list) -> bool:
    """
    Prüft, ob es ein AUX mit Tense=Pres gibt, das dieses Partizip als head_text hat.
    Wenn ja, markiere "PerfectoCompuesto" und liefere True.
    """
    part_text_lower = part_word["text"].lower()
    for sibling in seg_words:
        if sibling is part_word:
            continue
        if sibling.get("pos") == "AUX":
            morph = sibling.get("morph", {})
            if "Pres" in morph.get("Tense", []) and sibling.get("head_text", "").lower() == part_text_lower:
                set_past_tense_type(part_word, "PerfectoCompuesto")
                return True
    return False


def classify_past_tense_form(w_obj: dict, seg_words: list):
    """
    Prüft, ob Tense=Past => Kennzeichnung als PerfectoSimple, PerfectoCompuesto, etc.
    """
    morph = w_obj.get("morph", {})
    if not isinstance(morph, dict):
        return
    tense_vals = morph.get("Tense", [])
    verbform_vals = morph.get("VerbForm", [])
    if "Past" not in tense_vals:
        return
    # PerfectoSimple => Tense=Past + VerbForm=Fin
    if "Fin" in verbform_vals:
        set_past_tense_type(w_obj, "PerfectoSimple")
        return
    # Partizip => Tense=Past + VerbForm=Part
    if "Part" in verbform_vals:
        aux_raw = w_obj.get("head_text", "").lower()
        if aux_raw in PRESENT_FORMS:
            set_past_tense_type(w_obj, "PerfectoCompuesto")
        elif aux_raw in IMPERFECT_FORMS:
            set_past_tense_type(w_obj, "Pluscuamperfecto")
        elif aux_raw in FUTURE_FORMS:
            set_past_tense_type(w_obj, "FuturoPerfecto")
        elif aux_raw in COND_FORMS:
            set_past_tense_type(w_obj, "CondicionalPerfecto")
        elif detect_compound_any_fallback(w_obj, seg_words):
            return
        else:
            set_past_tense_type(w_obj, "OtroCompuesto")
        return
    # Falls Past, aber weder Fin noch Part => "PastOther"
    set_past_tense_type(w_obj, "PastOther")


def post_process_compound_tenses(data: dict):
    """
    Durchläuft alle Segmente/Wörter und verfeinert Vergangenheitsformen.
    """
    for seg in data.get("segments", []):
        seg_words = seg.get("words", [])
        for w_obj in seg_words:
            morph = w_obj.get("morph", {})
            if not isinstance(morph, dict):
                continue
            if "Past" in morph.get("Tense", []):
                classify_past_tense_form(w_obj, seg_words)

# -----------------------------------------------------------------------------
# Zukunftsformen-Erkennung (analytisches Futur)
# -----------------------------------------------------------------------------
IR_PRESENT_FORMS    = {"voy", "vas", "va", "vamos", "vais", "van"}
IR_IMPERFECT_FORMS = {"iba", "ibas", "íbamos", "ibais", "iban"}


def set_future_type(w_obj: dict, label: str):
    """
    Setzt ein benutzerdefiniertes Feld 'Future_Type' im Morph-Objekt.
    """
    if not isinstance(w_obj.get("morph"), dict):
        w_obj["morph"] = {}
    w_obj["morph"]["Future_Type"] = label


def post_process_compound_futures(data: dict):
    for seg in data.get("segments", []):
        words = seg.get("words", [])
        for i in range(len(words) - 2):
            w1, w2, w3 = words[i], words[i+1], words[i+2]

            pos1 = w1.get("pos")
            morph1 = w1.get("morph", {})
            pos2 = w2.get("pos")
            txt2 = w2.get("text", "").lower()
            pos3 = w3.get("pos")
            morph3 = w3.get("morph", {})

            # prüfe auf analytisches Futur: ir (AUX + Tense) + a + Infinitiv
            if (
                pos1 == "AUX"
                and "Tense" in morph1
                and txt2 == "a"
                and pos2 == "ADP"
                and pos3 == "VERB"
                and "Inf" in morph3.get("VerbForm", [])
            ):
                tense1 = morph1["Tense"]
                label = None
                if "Pres" in tense1:
                    label = "analyticalFuture"
                elif "Imp" in tense1:
                    label = "analyticalFuture_past"
                if label:
                    w3.setdefault("morph", {})
                    w3["morph"]["Future_Type"] = label

# -----------------------------------------------------------------------------
# Hauptroutine: Entfernen + Annotation + Post-Processing
# -----------------------------------------------------------------------------

def annotate_file(path, progress):
    data = json.load(open(path, "r", encoding="utf-8"))
    segs = data.get("segments", [])
    # Alte Annotationen löschen
    for s in segs:
        for w in s.get("words", []):
            for k in ("pos", "lemma", "dep", "head_text", "morph"):
                w.pop(k, None)
    # Annotation
    for s in segs:
        wl = s.get("words", [])
        if not wl:
            continue
        sl = split_into_sentences(wl)
        for i, sent in enumerate(sl):
            ctx = (sl[i-1] if i>0 else []) + sent + (sl[i+1] if i<len(sl)-1 else [])
            doc = nlp(" ".join(w.get("text", "").lower() for w in ctx))
            tok = 0
            for w in sent:
                txt = w.get("text", "")
                # foreign überspringen
                if w.get("foreign") == "1":
                    progress["annotated"] += 1
                    continue
                # Abgebrochene Wörter (inkl. nachfolgender Satzzeichen, z.B. "tu-,")
                if txt.endswith("-"):
                    w["pos"] = "self-correction"
                    progress["annotated"] += 1
                    show_progress(progress)
                    continue
                # Interjektion ee h
                if txt.lower() == "eeh":
                    w.update({"pos":"INTJ","lemma":txt,"dep":"","head_text":"","morph":{}})
                    progress["annotated"] += 1
                    continue
                while tok<len(doc) and (doc[tok].is_punct or doc[tok].is_space):
                    tok += 1
                if (tok<len(doc) and
                    strip_punct(doc[tok].text.lower()) == strip_punct(txt.lower())):
                    fill_word_annotation(w, doc[tok])
                    tok += 1
                else:
                    td = tok; found=False
                    while td < len(doc):
                        if (not(doc[td].is_punct or doc[td].is_space) and
                            strip_punct(doc[td].text.lower()) == strip_punct(txt.lower())):
                            fill_word_annotation(w, doc[td])
                            td += 1; found=True; break
                        td += 1
                    tok = td
                    if not found:
                        fb = annotate_fallback(strip_punct(txt.lower()))
                        w.update({
                            "pos": fb["pos"],
                            "lemma": fb["lemma"],
                            "dep": fb["dep"],
                            "head_text": fb["head_text"],
                            "morph": fb["morph"]
                        })
                progress["annotated"] += 1

    # Post-Processing
    post_process_compound_tenses(data)
    post_process_compound_futures(data)

    # Speichern
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

# -----------------------------------------------------------------------------
# Main: Auswahl und Durchlauf
# -----------------------------------------------------------------------------

def main():
    # Pfadcheck
    if not os.path.isdir(GRABACIONES_DIR):
        print(f"Ordner '{GRABACIONES_DIR}' nicht gefunden (erwartet in: {GRABACIONES_DIR})")
        return

    all_files = sorted(f for f in os.listdir(GRABACIONES_DIR) if f.lower().endswith(".json"))
    if not all_files:
        print(f"Keine JSON-Dateien im Ordner '{GRABACIONES_DIR}' gefunden.")
        return

    choice = input("Möchten Sie alle JSON-Dateien annotieren (all) oder eine bestimmte Anzahl (Zahl)?: ").strip().lower()
    if choice == "all":
        files_to_process = all_files
    elif choice.isdigit():
        files_to_process = all_files[:int(choice)]
    else:
        print("Ungültige Eingabe. Bitte 'all' oder eine Zahl eingeben.")
        return

    overwrite_choice = input("Sollen bestehende Annotationen überschrieben werden? (ja/nein): ").strip().lower()
    overwrite_existing = overwrite_choice == "ja"

    # Wortzählung
    total_words_to_annotate = 0
    filtered_files = []

    for fname in files_to_process:
        file_path = os.path.join(GRABACIONES_DIR, fname)
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            segments = data.get("segments", [])
            if not overwrite_existing and already_annotated(segments):
                print(f"Datei {fname} ist bereits annotiert, wird übersprungen.")
                continue
            filtered_files.append(fname)
            for seg in segments:
                total_words_to_annotate += len(seg.get("words", []))

    if not filtered_files:
        print("Keine Dateien zum Annotieren gefunden.")
        return

    print(f"Insgesamt {len(filtered_files)} JSON-Dateien mit {total_words_to_annotate} Wörtern zu annotieren...")

    progress_data = {
        "annotated": 0,
        "total": total_words_to_annotate,
        "last_step": 0  # Für 2500er-Schritte
    }

    # Bearbeitung
    for fname in filtered_files:
        file_path = os.path.join(GRABACIONES_DIR, fname)
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            words_in_file = sum(len(seg.get("words", [])) for seg in data.get("segments", []))
        print(f"\nBearbeite Datei: {fname}  ({words_in_file} Wörter)")
        annotate_file(file_path, progress_data)
        file_finished_message(progress_data)

    print("\nAlle gewünschten Dateien wurden bearbeitet.")
    print(f"Insgesamt {progress_data['annotated']} Wörter annotiert.")
    print("Tipp: Für statistische Auswertungen bitte analysis_pasado.py o.Ä. verwenden.\n")

if __name__ == "__main__":
    main()
