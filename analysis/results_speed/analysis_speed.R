# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Felix Tacke

# analysis_speed.R — CORAPAN‑Projekt
# =================================================
#
# Dieses Skript führt eine Ein-Skript-Auswertung der Artikulations- und Sprechrate
# in professionellen Sprecher:innen der Aufnahmen des CORAPAN-Korpus durch. Es berechnet 
# Pausenanteile und speichert die Ergebnisse als CSV-Tabellen und PNG-Plots im Ordner ./output/.
#
# -----------------------------------------------------------------------------
# 1. Begriffsdefinitionen
# -----------------------------------------------------------------------------
# * Artikulations-Rate (AR): Geschwindigkeit der Lautproduktion ohne Pausen,
#   berechnet aus der Nettosprechzeit (Summe aller Wortdauern innerhalb eines Segments).
# * Sprech-Rate (SR): Tempo inklusive natürlicher Kurzpausen, Segmentdauer =
#   last_end – first_start pro fortlaufendem Sprechersegment.
#
# -----------------------------------------------------------------------------
# 2. Kategorisierung & Filter
# -----------------------------------------------------------------------------
# Die Auswertung unterscheidet die Modi libre und lectura sowie Geschlechter.
# Buckets mit weniger als 10 Wörtern werden verworfen, um Varianzen bei Kleinstproben
# zu vermeiden.
#
# -----------------------------------------------------------------------------
# 3. Berechnete Kennzahlen pro Bucket
# -----------------------------------------------------------------------------
# * *_wpm: Wörter pro Minute
# * *_min: zugrundeliegende Minuten (AR: Nettozeit, SR: Segmentzeit)
# * *_words: Wortanzahl (für Transparenz der Gewichtung)
#
# -----------------------------------------------------------------------------
# 4. Ausgabedateien (im Ordner ./output/)
# -----------------------------------------------------------------------------
# | Datei                          | Inhalt                                  | Mittelung          |
# |-------------------------------|----------------------------------------|--------------------|
# | articulation_speed_by_file.csv | eine Zeile pro JSON; alle Buckets + Minuten + Wortzahl | –                  |
# | speech_speed_by_file.csv       | dito für SR                            | –                  |
# | articulation_speed_by_country.csv | Summe aller Dateien desselben 2-/3-stelligen country_code | Gewichtetes Mittel (Σ Wörter / Σ Zeit) |
# | speech_speed_by_country.csv    | dito für SR                           | vgl. oben          |
#
# Alle CSVs sind UTF-8, Feldtrennung ;, fehlende Buckets erhalten den Wert NA.
#
# -----------------------------------------------------------------------------
# 5. Implementierungsdetails
# -----------------------------------------------------------------------------
# * Pfadkonstanten entsprechen analysis_tenses.R (BASE_WEB, GRABACIONES_DIR usw.).
# * Unterordner ./output/ wird bei Bedarf erstellt.
# * Minuten/Zeitberechnung in Sekunden; Umrechnung erfolgt erst beim Schreiben.
# * Aggregation pro Land: Country-Code wird prioritär aus data['country_code'] gelesen;
#   Fallback ist ein RegEx-Match auf den Dateinamen. Existiert beides nicht, wird UNK vergeben.
# * Lizenz: MIT (© 2025 Felix Tacke).
#
# -----------------------------------------------------------------------------
# 6. Reproduzierbarkeit & Zitation
# -----------------------------------------------------------------------------
# Zur wissenschaftlichen Dokumentation genügen folgende Angaben:
# * Korpus: CORAPAN-Speed, Release 2025-05 (Transkripte entsprechen Whisper v3.2, Tokenisierung NLTK 3.9).
# * Auswahlkriterien: professionelle SprecherInnen, mind. 10 Wörter / Bucket.
# * Definition der Tempometriken s.o. (Formeln 1 & 2). AR basiert auf Nettozeit, SR auf Segmentzeit (Pausen ≥ ASR-Schnitt).
# * Berechnungs- und Aggregationsskript: analysis_speed.R (dieses Dokument).
#
# -----------------------------------------------------------------------------


# 1 | Pakete -----------------------------------------------------------------
suppressPackageStartupMessages({
  library(tidyverse)   # ggplot2, readr, dplyr, tidyr, forcats
  library(janitor)     # clean_names()
})

# 2 | I/O-Hilfen -------------------------------------------------------------
out_dir <- "output"
if (!dir.exists(out_dir)) dir.create(out_dir)

save_csv  <- function(x, name) write_csv(x, file.path(out_dir, name))
save_plot <- function(p, name, w = 9, h = 6)
  ggsave(file.path(out_dir, name), p, width = w, height = h, dpi = 300)

# 3 | Daten laden & vorbereiten ---------------------------------------------
ar <- read_csv2("articulation_speed_by_country.csv") %>% clean_names()
sr <- read_csv2("speech_speed_by_country.csv")       %>% clean_names()

# ------------------------------------------------------------
# Benutzerdefinierte Länderauswahl
# ------------------------------------------------------------
# Hier können Sie angeben, welche Länder in die Analyse einbezogen
# bzw. ausgeschlossen werden sollen. Passen Sie die Vektoren
# 'included_countries' und 'excluded_countries' nach Bedarf an.
#
# Verfügbare Ländercodes in den Daten:
# "ARG", "ARG-Cba", "ARG-Cht", "ARG-SdE", "BOL", "CHI", "COL", "CR", "CUB",
# "ECU", "ES-CAN", "ES-MAD", "ES-SEV", "GUA", "HON", "MEX", "NIC", "PAN",
# "PAR", "PER", "RD", "SAL", "URU", "VEN"
#
# Beispiel:
# included_countries <- c("all")  # alle Länder einbeziehen, außer ausgeschlossene
# excluded_countries <- c("ARG-Cba", "ARG-Cht")
#
# Oder nur bestimmte Länder einbeziehen:
# included_countries <- c("ARG", "BOL", "CHI")
#
# Wenn 'included_countries' "" (leer) ist, werden alle Länder außer den
# ausgeschlossenen berücksichtigt.
#
included_countries <- c()  # oder "" leer
excluded_countries <- c("ARG-Cba","ARG-Cht","ARG-SdE","ES-SEV","ES-CAN")

# Funktion: gewichtetes Mittel über Geschlechter per Modus -------------------
w_mean <- function(f_wpm, f_min, m_wpm, m_min) {
  (f_wpm * f_min + m_wpm * m_min) / (f_min + m_min)
}

# Artikulation (AR) ----------------------------------------------------------
art <- ar %>% 
  filter(
    if ("all" %in% included_countries) {
      !country %in% excluded_countries
    } else if (length(included_countries) > 0) {
      country %in% included_countries
    } else {
      !country %in% excluded_countries
    }
  ) %>%
  transmute(
    country,
    libre   = w_mean(libre_f_wpm,   libre_f_min,
                     libre_m_wpm,   libre_m_min),
    lectura = w_mean(lectura_f_wpm, lectura_f_min,
                     lectura_m_wpm, lectura_m_min)
  ) %>% mutate(delta = libre - lectura) %>% as_tibble()

save_csv(art, "articulation_libre_lectura_stats.csv")

# Plot AR: Dumbbell ----------------------------------------------------------
p_art <- art %>%
  pivot_longer(c(libre, lectura),
               names_to = "mode", values_to = "wpm") %>%
  ggplot(aes(wpm, fct_reorder(country, wpm), colour = mode)) +
  geom_line(aes(group = country), colour = "grey70") +
  geom_point(size = 3) +
  labs(title = "Artikulationsrate: gelesen vs. frei",
       x = "Wörter pro Minute", y = NULL, colour = "Modus") +
  theme_minimal(base_size = 12)
save_plot(p_art, "articulation_libre_lectura_plot.png")

# ─ Einzel-Plot: Artikulation libre ───────────────────────────────
p_art_libre <- art %>% 
  ggplot(aes(libre,
             fct_reorder(country, libre))) +
  geom_col(width = .6, fill = "steelblue") +
  labs(title = "Articulation rate – libre",
       x = "Words per minute", y = NULL) +
  theme_minimal(base_size = 12)

save_plot(p_art_libre, "articulation_libre_plot.png")

# ─ Einzel-Plot: Artikulation lectura ─────────────────────────────
p_art_lect <- art %>% 
  ggplot(aes(lectura,
             fct_reorder(country, lectura))) +
  geom_col(width = .6, fill = "firebrick") +
  labs(title = "Articulation rate – lectura",
       x = "Words per minute", y = NULL) +
  theme_minimal(base_size = 12)

save_plot(p_art_lect, "articulation_lectura_plot.png")

# Sprechrate (SR) ------------------------------------------------------------
sp <- sr %>% 
  filter(
    if ("all" %in% included_countries) {
      !country %in% excluded_countries
    } else if (length(included_countries) > 0) {
      country %in% included_countries
    } else {
      !country %in% excluded_countries
    }
  ) %>%
  transmute(
    country,
    libre   = w_mean(libre_f_wpm,   libre_f_min,
                     libre_m_wpm,   libre_m_min),
    lectura = w_mean(lectura_f_wpm, lectura_f_min,
                     lectura_m_wpm, lectura_m_min)
  ) %>% mutate(delta = libre - lectura) %>% as_tibble()

save_csv(sp, "speech_libre_lectura_stats.csv")

# Plot SR: Dumbbell ----------------------------------------------------------
p_sp <- sp %>%
  pivot_longer(c(libre, lectura),
               names_to = "mode", values_to = "wpm") %>%
  ggplot(aes(wpm, fct_reorder(country, wpm), colour = mode)) +
  geom_line(aes(group = country), colour = "grey70") +
  geom_point(size = 3) +
  labs(title = "Sprechrate: gelesen vs. frei",
       x = "Wörter pro Minute", y = NULL, colour = "Modus") +
  theme_minimal(base_size = 12)
save_plot(p_sp, "speech_libre_lectura_plot.png")

# ─ Einzel-Plot: Sprechrate libre ────────────────────────────────
p_sp_libre <- sp %>% 
  ggplot(aes(libre,
             fct_reorder(country, libre))) +
  geom_col(width = .6, fill = "steelblue") +
  labs(title = "Speech rate – libre",
       x = "Words per minute", y = NULL) +
  theme_minimal(base_size = 12)

save_plot(p_sp_libre, "speech_libre_plot.png")

# ─ Einzel-Plot: Sprechrate lectura ──────────────────────────────
p_sp_lect <- sp %>% 
  ggplot(aes(lectura,
             fct_reorder(country, lectura))) +
  geom_col(width = .6, fill = "firebrick") +
  labs(title = "Speech rate – lectura",
       x = "Words per minute", y = NULL) +
  theme_minimal(base_size = 12)

save_plot(p_sp_lect, "speech_lectura_plot.png")

# 4 | Pausenanteil -----------------------------------------------------------
pauses <- art %>%                        # AR-Tabelle
  dplyr::select(country, libre_ar = libre, lectura_ar = lectura) %>%
  left_join(sp %>%                       # SR-Tabelle
              dplyr::select(country, libre_sr = libre, lectura_sr = lectura),
            by = "country") %>%
  mutate(
    pause_libre   = 1 - libre_sr   / libre_ar,
    pause_lectura = 1 - lectura_sr / lectura_ar,
    delta_pause   = pause_lectura - pause_libre
  )

save_csv(dplyr::select(pauses, country, pause_libre, pause_lectura, delta_pause),
         "pauses_libre_lectura_stats.csv")

# Plot Pausen: zwei Balken je Land ------------------------------------------
p_pause <- pauses %>%
  pivot_longer(c(pause_libre, pause_lectura),
               names_to = "mode", values_to = "pause_share") %>%
  mutate(mode = recode(mode,
                       pause_libre = "libre",
                       pause_lectura = "lectura")) %>%
  ggplot(aes(pause_share,
             fct_reorder(country, pause_share),
             fill = mode)) +
  geom_col(position = "dodge") +
  scale_x_continuous(labels = scales::percent_format(accuracy = 1)) +
  labs(title = "Pause share of speech time (libre vs. lectura)",
       x = "Share of pause time", y = NULL, fill = "Mode") +
  theme_minimal(base_size = 12)
save_plot(p_pause, "pauses_libre_lectura_plot.png")

# ─ Einzel-Plot: Pausenanteil libre ───────────────────────────────
p_pause_libre <- pauses %>% 
  ggplot(aes(pause_libre,
             fct_reorder(country, pause_libre))) +
  geom_col(width = .6, fill = "steelblue") +
  scale_x_continuous(labels = scales::percent_format(accuracy = 1)) +
  labs(title = "Pause share – libre",
       x = "Share of pause time", y = NULL) +
  theme_minimal(base_size = 12)

save_plot(p_pause_libre, "pauses_libre_plot.png")

# ─ Einzel-Plot: Pausenanteil lectura ─────────────────────────────
p_pause_lect <- pauses %>% 
  ggplot(aes(pause_lectura,
             fct_reorder(country, pause_lectura))) +
  geom_col(width = .6, fill = "firebrick") +
  scale_x_continuous(labels = scales::percent_format(accuracy = 1)) +
  labs(title = "Pause share – lectura",
       x = "Share of pause time", y = NULL) +
  theme_minimal(base_size = 12)

save_plot(p_pause_lect, "pauses_lectura_plot.png")

# 5 | Minimaler Hypothesentest (Ausgabe Konsole) ----------------------------
cat("\n——  Paired t-Test: does reading aloud cause more pauses?  ——\n")
print(t.test(pauses$pause_lectura, pauses$pause_libre, paired = TRUE))

# ─────────────────────────  Ende  ──────────────────────────────────────────
