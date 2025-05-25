# CO.RA.PAN-Tools Übersicht

Dieses Repository enthält Tools zur Datenverarbeitung und Analyse des CO.RA.PAN-Korpus.  
Die bearbeiteten Daten sind Transkriptionen gesprochener Sprache in Form von JSON-Dateien, die eine detaillierte Segmentierung in Sprechersegmente und Wörter mit linguistischen Annotationen (POS, Lemma, Morphologie) aufweisen. JSON als Format ermöglicht eine flexible, hierarchische und erweiterbare Struktur, die sich besonders gut eignet, um sprachliche Daten mit vielfältigen Informationen anzureichern und maschinell auszuwerten.

Das Repository umfasst ausschließlich Python- und R-Skripte, die für die Aufbereitung, Verarbeitung und Auswertung der sprachlichen Daten entwickelt wurden.

## Inhalt

- Python-Skripte zur Datenverarbeitung und Annotation (z.B. im Ordner `analysis/` und `annotation/`)
- R-Skripte zur statistischen Analyse und Visualisierung (im Ordner `analysis/results/`)
- Keine Rohdaten oder Analyseergebnisse (CSV, PNG, DOCX) sind im Repository enthalten, diese werden separat verwaltet.

## CO.RA.PAN-Korpora

Das CO.RA.PAN-Projekt umfasst zwei Korpora:

- **Full Corpus (Restricted)**  
  Vollständiges Korpus mit Audio- und Transkriptionsdaten. Zugriff nur auf Anfrage.  
  DOI: https://doi.org/10.5281/zenodo.15360942

- **Sample Corpus (Public)**  
  Öffentliches Beispielkorpus mit ausgewählten Audios und JSON-Daten.  
  DOI: https://doi.org/10.5281/zenodo.15378479

Das *Full Corpus* wird von der CO.RA.PAN-Webapp genutzt und ist nicht Teil dieses Repository.

## Ziel

Die Tools dienen der Vorbereitung, Analyse und Auswertung des CO.RA.PAN-Korpus, um linguistische Fragestellungen zu untersuchen.  
Das Repository ist als Ergänzung zur CO.RA.PAN-Webapp konzipiert, die die Daten visualisiert und zugänglich macht.

## Projektstruktur

- `analysis/`  
  Python- und R-Skripte zur Analyse der Zeitformen und anderer linguistischer Merkmale.  
  Enthält auch einen `results/`-Ordner mit Analyseergebnissen, der nicht versioniert wird.

- `annotation/`  
  Skripte und Hilfsmittel zur Annotation der Daten.

- `database/`  
  Skripte zur Erstellung und Verwaltung der Datenbank.

## Nutzung

1. Repository klonen  
   ```bash
   git clone <URL zu CO.RA.PAN-Tools>
   ```

2. Python-Umgebung einrichten  
   Abhängigkeiten entsprechend den Skripten installieren (z.B. mit `pip`).

3. Skripte ausführen  
   Die Python- und R-Skripte können zur Datenverarbeitung und Analyse genutzt werden.

## Hinweise

- Analyseergebnisse und Rohdaten sind nicht Teil dieses Repositories und werden separat verwaltet.  
- Für die Web-App und weitere Informationen siehe das Hauptprojekt CO.RA.PAN:  
  https://hispanistica.online.uni-marburg.de/corapan/

## Wichtige DOIs der zugehörigen Repositories

- CO.RA.PAN Web-App (Code): https://doi.org/10.5281/zenodo.15359652  
- CO.RA.PAN Full Corpus (Restricted): https://doi.org/10.5281/zenodo.15360942  
- CO.RA.PAN Sample Corpus (Public): https://doi.org/10.5281/zenodo.15378479

## Lizenz

Dieses Repository ist unter der MIT-Lizenz freigegeben.  
Siehe die Datei [LICENSE](LICENSE) für Details.

---

*Dieses Repository enthält ausschließlich Quellcode für Tools zur Datenverarbeitung und Analyse des CO.RA.PAN-Korpus.*
