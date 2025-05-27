# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Felix Tacke

# analysis_tenses_corapan.R — CORAPAN‑Projekt
# =================================================
#
# Dieses Skript analysiert die Tempora Futuro & Pasado in zwei Speech-Types:
# oral/lectura und oral/libre im CORAPAN-Korpus.
#
# -----------------------------------------------------------------------------
# 1. Analyseinhalte
# -----------------------------------------------------------------------------
# * Proportionale Verteilungen der Varianten (analytical, synthetic)
# * Δ-Plots (Libre – Reading)
# * Fisher-Test und Odds Ratio zur Effektgröße
#
# -----------------------------------------------------------------------------
# 2. Label-Konventionen (englisch)
# -----------------------------------------------------------------------------
# * speech_type: oral/lectura | oral/libre
# * variant: analytical | synthetic
#
# -----------------------------------------------------------------------------
# 3. Pfad- und Dateikonventionen
# -----------------------------------------------------------------------------
# * Ergebnisse und Plots werden im Unterordner 'plots/tenses_corapan' gespeichert
# * Eingabedaten: 'tenses_tidy.csv'
#
# -----------------------------------------------------------------------------
# 4. Benutzerdefinierte Länderauswahl
# -----------------------------------------------------------------------------
# * Steuerung der einbezogenen Länder über included_countries und excluded_countries
#
# -----------------------------------------------------------------------------
# 5. Lizenz
# -----------------------------------------------------------------------------
# MIT (© 2025 Felix Tacke)
#
# -----------------------------------------------------------------------------
# 6. Hinweise
# -----------------------------------------------------------------------------
# * Schriftart Helvetica für Plots
# * Nur Summenzeilen (file beginnt mit "SUM") werden analysiert
#

# --------------------------- PAKETE ------------------------------------------
required_pkgs <- c("tidyverse", "patchwork", "broom", "stringr", "stringi")
need <- required_pkgs[!vapply(required_pkgs, requireNamespace,
                              quietly = TRUE, FUN.VALUE = logical(1))]
if (length(need))
  stop("Bitte installiere die Pakete: ", paste(need, collapse = ", "))
invisible(lapply(required_pkgs, library, character.only = TRUE))
theme_set(theme_minimal(base_family = "Helvetica"))

# --------------------------- PFADSETUP ---------------------------------------
this_file   <- tryCatch(normalizePath(sys.frames()[[1]]$ofile),
                        error = function(e) getwd())
results_dir <- dirname(this_file)
plots_dir   <- file.path(results_dir, "plots", "tenses_corapan")
if (!dir.exists(plots_dir)) dir.create(plots_dir, recursive = TRUE)

speech_path <- file.path(results_dir, "tenses_tidy.csv")
if (!file.exists(speech_path))
  stop("tenses_tidy.csv nicht gefunden – prüfe Pfad!")

# --------------------------- DATEN LADEN -------------------------------------
rename_map <- c(Country="country", filename="file", Filename="file",
                Mode="mode", Tense="tense", Variant="variant",
                Tokens="tokens", count="tokens")

read_and_clean <- function(path){
  raw <- readr::read_csv(path, show_col_types = FALSE)
  names(raw) <- dplyr::coalesce(rename_map[names(raw)], names(raw))
  stopifnot(all(c("country","file","mode","tense","variant","tokens") %in% names(raw)))
  raw
}

raw <- read_and_clean(speech_path)

# ----------- VARIANT-LABELS & SPEECH_TYPE (Akzente/Leerzeichen egal) -----------
raw <- raw %>%
  mutate(
    variant = stri_trans_general(variant, "Latin-ASCII") |> str_to_lower(),
    variant = if_else(str_detect(variant, "anal"), "analytical",
               if_else(str_detect(variant, "sint|syn"), "synthetic", variant))
  ) %>%
  rename(speech_type = mode)

speech_type_levels <- c("lectura", "libre")

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
# Wenn 'included_countries' "all" ist, werden alle Länder außer den
# ausgeschlossenen berücksichtigt.
#
included_countries <- c("ARG","BOL","ES-MAD","MEX","PAR","PER","RD")  # oder "all"
excluded_countries <- c("ARG-Cba","ARG-Cht","ARG-SdE","ES-SEV","ES-CAN")

suffix <- if ("all" %in% included_countries) {
  "_all"
} else {
  paste0("_", paste(included_countries, collapse = "_"))
}

f <- raw %>%
  filter(str_detect(file, "^SUM")) %>%               # nur Summen-Zeilen
  filter(speech_type %in% speech_type_levels,
         tense %in% c("future","pasado")) %>%        # Datensätze heißen future / pasado
  filter(
    if ("all" %in% included_countries) {
      !country %in% excluded_countries
    } else if (length(included_countries) > 0) {
      country %in% included_countries
    } else {
      !country %in% excluded_countries
    }
  )
if (nrow(f) == 0) stop("Kein Datensatz nach Filter!")

# ----------------  AGGREGATION & PROPORTION  ---------------------------------
summary <- f %>%
  group_by(country, tense, speech_type, variant) %>%
  summarise(tokens = sum(tokens), .groups = "drop") %>%
  group_by(country, tense, speech_type) %>%
  mutate(total = sum(tokens),
         prop  = tokens / total,
         prop_percent = prop * 100) %>%
  ungroup() %>%
  mutate(
    speech_type = recode(speech_type,
                         "lectura" = "oral/lectura",
                         "libre"   = "oral/libre"),
    speech_type = factor(speech_type,
                         levels = c("oral/lectura","oral/libre"))
  )

# ----------------  Δ-WERTE & EFFEKTGRÖSSEN  -----------------------------------
analytic <- summary %>%
  filter(variant == "analytical") %>%
  mutate(type_raw = recode(speech_type,
                           "oral/lectura" = "lectura",
                           "oral/libre"   = "libre")) %>%
  select(country, tense, type_raw, prop)

delta_df <- analytic %>%
  pivot_wider(names_from = type_raw,
              values_from = prop,
              names_prefix = "prop_",
              values_fill = 0) %>%
  mutate(delta_ll = (prop_libre - prop_lectura) * 100)

tokens_wide <- summary %>%
  mutate(type_raw = recode(speech_type,
                           "oral/lectura" = "lectura",
                           "oral/libre"   = "libre")) %>%
  select(country, tense, type_raw, variant, tokens) %>%
  pivot_wider(names_from = c(type_raw, variant),
              values_from = tokens,
              names_sep   = "_",
              values_fill = 0)

for(col in c("libre_analytical","libre_synthetic",
             "lectura_analytical","lectura_synthetic")){
  if(! col %in% names(tokens_wide)) tokens_wide[[col]] <- 0
}

effect_sizes <- tokens_wide %>%
  mutate(
    odds_ll = ((libre_analytical + .5)/(libre_synthetic + .5)) /
              ((lectura_analytical + .5)/(lectura_synthetic + .5)),
    fisher_ll = pmap_dbl(list(libre_analytical, libre_synthetic,
                              lectura_analytical, lectura_synthetic),
                         \(a,b,c,d) fisher.test(matrix(c(a,b,c,d), 2, byrow = TRUE))$p.value)
  ) %>%
  select(country, tense, odds_ll, fisher_ll) %>%
  left_join(delta_df %>% select(country, tense, delta_ll),
            by = c("country","tense"))

# ---------------------------  PLOT-FUNKTIONEN  -------------------------------
plot_w <- 10; plot_h <- 7
tense_map <- c("pasado" = "Past", "future" = "Future")

plot_proportions <- function(data, tense_lab, out){

  d <- data %>%                       # Hilfsspalten für flexible Labels
    mutate(label   = sprintf("%.1f%%", prop_percent),
           vjust   = ifelse(prop_percent > 95, 1.3, -0.25),  # >95 % → nach innen
           lbl_col = ifelse(prop_percent > 95, "white", "black"))

  p <- ggplot(d, aes(country, prop_percent, fill = variant)) +
    geom_col(position = position_dodge(.9), width = .8) +
    geom_text(aes(label   = label,
                  vjust   = vjust,
                  colour  = lbl_col),
              position = position_dodge(.9), size = 2.5,
              show.legend = FALSE) +
    scale_colour_identity() +                         # nutzt lbl_col
    scale_y_continuous(limits = c(0, 105), expand = c(0, 0)) +
    facet_wrap(~ speech_type, ncol = 1) +
    labs(title = glue::glue("{tense_map[[tense_lab]]} tense · variant distribution by speech type"),
         x = "Country", y = "Share (%)", fill = "Variant") +
    theme(axis.text.x = element_text(angle = 45, hjust = 1),
          legend.position = "bottom")

  ggsave(out, p, width = plot_w, height = plot_h, dpi = 300)
}

plot_delta <- function(data, tense_lab, out){
  p <- ggplot(data, aes(country, delta_ll, fill = delta_ll > 0)) +
    geom_col(width = .7, show.legend = FALSE) +
    geom_hline(yintercept = 0, linewidth = .4, linetype = "dashed") +
    geom_text(aes(label = sprintf("%+.1f", delta_ll)),
              vjust = ifelse(data$delta_ll >= 0, -0.4, 1.3), size = 3) +
    scale_y_continuous(expand = expansion(mult = .1)) +
    scale_fill_manual(values = c("TRUE"="steelblue","FALSE"="indianred")) +
    labs(title = glue::glue("Libre – Reading: Δ analytical share ({tense_map[[tense_lab]]})"),
         x = "Country", y = "Δ percentage points",
         caption = "positive = Libre more analytical") +
    theme(axis.text.x = element_text(angle = 45, hjust = 1))
  ggsave(out, p, width = plot_w, height = plot_h, dpi = 300)
}

plot_heatmap <- function(data, tense_lab, out){
  d <- data %>% filter(variant == "analytical") %>%
    mutate(prop_pct = round(prop * 100, 1))
  p <- ggplot(d, aes(speech_type, forcats::fct_rev(country), fill = prop_pct)) +
    geom_tile(color = "white") +
    geom_text(aes(label = prop_pct), size = 3) +
    scale_fill_gradient(limits = c(0,100),
                        low = "white", high = "steelblue",
                        name = "Analytical (%)") +
    labs(title = glue::glue("Analytical share (%) – {tense_map[[tense_lab]]} tense"),
         x = "Speech type", y = "Country") +
    theme(axis.text.x = element_text(angle = 45, hjust = 1))
  ggsave(out, p, width = plot_w, height = plot_h, dpi = 300)
}

# -------------- FUNKTION: Variant-Mode-Balken (2 Speech-Types) ---------------
plot_variant_mode <- function(data, tense_lab, variant_lab, out){

  d <- data %>%                                      # Tempus + Variante
    filter(tense == tense_lab,                       # << neu
           variant == variant_lab) %>%               # unverändert
    mutate(label   = sprintf("%.1f%%", prop_percent),
           vjust   = ifelse(prop_percent > 95, 1.3, -0.25),
           lbl_col = ifelse(prop_percent > 95, "white", "black"))

  p <- ggplot(d, aes(country, prop_percent, fill = speech_type)) +
    geom_col(position = position_dodge(.8), width = .7) +
    geom_text(aes(label = label, vjust = vjust, colour = lbl_col),
              position = position_dodge(.8), size = 2.5, show.legend = FALSE) +
    scale_colour_identity() +
    scale_y_continuous(limits = c(0, 105), expand = c(0, 0)) +
    labs(title = glue::glue("{str_to_title(variant_lab)} form · {tense_map[[tense_lab]]} tense"),
         x = "Country", y = "Share (%)", fill = "Speech type") +
    theme(axis.text.x = element_text(angle = 45, hjust = 1))

  ggsave(out, p, width = plot_w, height = plot_h, dpi = 300)
}

# ----------------  VARIANT-MODE-PLOTS  ---------------------------------------
plot_variant_mode(summary, "pasado", "analytical",
                  file.path(plots_dir, paste0("VariantBar_Analytical_Pasado", suffix, ".png")))

plot_variant_mode(summary, "pasado", "synthetic",
                  file.path(plots_dir, paste0("VariantBar_Synthetic_Pasado", suffix, ".png")))

plot_variant_mode(summary, "future", "analytical",
                  file.path(plots_dir, paste0("VariantBar_Analytical_Futuro", suffix, ".png")))

plot_variant_mode(summary, "future", "synthetic",
                  file.path(plots_dir, paste0("VariantBar_Synthetic_Futuro", suffix, ".png")))

# -------------------------------  OUTPUT  ------------------------------------
plot_proportions(summary %>% filter(tense=="pasado"),
                 "pasado",
                 file.path(plots_dir, paste0("Proportion_Past", suffix, ".png")))
plot_proportions(summary %>% filter(tense=="future"),
                 "future",
                 file.path(plots_dir, paste0("Proportion_Future", suffix, ".png")))

plot_delta(effect_sizes %>% filter(tense=="pasado"),
           "pasado",
           file.path(plots_dir, paste0("Delta_Libre_vs_Lectura_Past", suffix, ".png")))
plot_delta(effect_sizes %>% filter(tense=="future"),
           "future",
           file.path(plots_dir, paste0("Delta_Libre_vs_Lectura_Future", suffix, ".png")))

plot_heatmap(summary %>% filter(tense=="pasado"),
             "pasado",
             file.path(plots_dir, paste0("Heatmap_Analytical_Past", suffix, ".png")))
plot_heatmap(summary %>% filter(tense=="future"),
             "future",
             file.path(plots_dir, paste0("Heatmap_Analytical_Future", suffix, ".png")))

readr::write_csv(effect_sizes,
                 file.path(plots_dir,
                           paste0("effect_sizes_livre_vs_lectura", suffix, ".csv")))

