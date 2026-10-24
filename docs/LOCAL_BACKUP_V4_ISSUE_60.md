# Lokalne kopie v4 — Issue #60

Baza implementacji: `origin/main` `2adab86092b34e47194bf76fbff40ff33bfe2d1f` (etapy A i B1).

W ekranie Dane dodano osobne „Pobierz kopię JSON v4” oraz „Podgląd pliku v4 (bez przywracania)”. Dotychczasowy przycisk JSON i importer v1/v2/v3 pozostają bez zmian. Nowe operacje działają lokalnie, również offline; moduły A/B1 oraz adapter są objęte allowlistą wydania i precache. Nie zmieniono stylów Matrix.

Eksport korzysta z kompletnego snapshotu istniejącego API bazy, bez konstruowania monolitycznej kopii v3 z osadzonymi archiwami dla natywnego dziennika. Dla starszego model bridge bez trainingJournal używa pełnego istniejącego eksportu modelu, aby nie pominąć metadanych spoza snapshotu v2. B1 kompresuje, weryfikuje i porównuje cały wynik przed wywołaniem pobrania. Błąd nie tworzy częściowego downloadu i nie uruchamia awaryjnego eksportu niepełnych danych.

Osobny input podglądu sprawdza rozmiar przed odczytem pliku, potem pełną walidację dekoderem A. Widok otrzymuje jedynie liczniki i podsumowanie, bez raw/staging. Nie tworzy kandydata restore ani przycisku potwierdzającego; wcześniejszy kandydat starszego importu zostaje odrzucony. Zamknięcie usuwa podsumowanie. Błędny kolejny plik nie pozostawia starego podglądu. Wybranie v4 w dotychczasowym importerze nadal bezpiecznie odrzuca nieobsługiwany format.

Nie zmieniono IndexedDB, modelu danych, produkcyjnego Google Drive, przywracania ani kontraktów A/B1. Eksport nie tworzy preimage. Archiwa, ich raw, kolejność, null i metadane zachowuje B1. Lokalne szkice i konfiguracja Drive pozostają na urządzeniu, poza kopią treningową, tak jak w starszych formatach; istnieje dotychczasowy osobny eksport szkiców. Issue #61 nie jest wdrażane.

## Weryfikacja

- Node: 143 testy PASS (w tym 3 nowe testy adaptera, ograniczenia rozmiaru i brak cichego fallbacku niepełnego bridge).
- Chromium: nowe testy produkcyjnych przycisków sprawdzają offline po reload, 390×844, dokładne zachowanie archiwum 4 MiB i null, brak overflow, odrzucenie uszkodzonej sumy kontrolnej, brak przywracania i pełną równość rekordów wszystkich store przed/po. Błąd kompresji nie pobiera pliku. Dodatkowy test natywnego v3 porównuje pełne data/catalog/archives i usuwa wcześniejszy kandydat restore.
- Pełna regresja Chromium i GitHub Actions: wynik w PR/opisie zadania po zakończeniu.
- `node --check` app/storage/indexeddb/sw, `build_release.py --check`, budowa `dist/issue-60`, `git diff --check`: PASS.

## Ograniczenia

To podgląd v4, nie przywracanie. Zachowano limity A/B1; brak gwarancji niskiego RAM lub natychmiastowego anulowania synchronicznych walidatorów. Mały skompresowany plik może wymagać dużo pamięci po rozwinięciu. Dane testowe są syntetyczne; rozmiar mobilny Chromium nie oznacza testu na fizycznym Androidzie. Nie testowano danych właściciela ani produkcyjnego konta Google i nie publikowano aplikacji.
