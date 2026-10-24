# Backup v5 C1 — Issue #66

Baza: main `148c8d4`. Plan nadrzędny, pełne Issue #66 i dokumentacja A/B1/v5 zostały przeczytane. Format, eksportery, istniejący dekoder i mechanizm produkcyjnego przywracania nie są zmieniane.

## Podgląd lokalny

W ekranie Dane osobny input „Podgląd kopii v5”. Przed odczytem obowiązuje limit pliku 32 MiB; właściwy `decodeBackup` z `backup-v5.mjs` sprawdza cały format i dotychczasowe budżety. Nie ma drugiej implementacji dekodera ani ominięcia checksum. Raport pokazuje liczbę planów, obecność aktywnej wersji, sesji, wyników, zapisanych pozycji serii, snapshotów i logicznych archiwów (w tym raw:null). Fragmenty nie są liczone jako archiwa. Nie wyświetla raw, ID ani etykiet pochodzących z kopii. Błędy parsera są zastępowane stałymi komunikatami, żeby fragment niepoprawnego JSON nie wyciekł do UI.

Użytkownik może anulować operację i zamknąć raport. Opóźniony wynik odrzuconej operacji nie wraca do ekranu. Nowy wybór usuwa poprzedni raport; błędny plik nie pozostawia starego sukcesu. Podgląd v5 odrzuca poprzedniego kandydata restore; wybór starego importu/podglądu/restore Drive zamyka v5. Kod nie daje przycisku nadpisania IndexedDB.

## Izolowana baza w pamięci

Nowy `backup-v5-preview.mjs` importuje istniejący reader, nie importuje IndexedDB ani modułu Drive. `createTrialDatabase` jest nietrwałą bazą obiektową z rewizją, odłączonymi odczytami i atomowym zatwierdzeniem. Dostaje wyłącznie zweryfikowany staging. Przygotowuje kopię całej odczytanej struktury, sprawdza przerwanie/rewizję, odczytuje odłączoną kopię i porównuje rekurencyjnie wszystkie własne klucze, typy i wartości, w tym dokładną równość stringów raw. Nie serializuje wielkich raw do canonical JSON w celu porównania.

Wcześniejszy stan trial nie zmienia się przy przerwaniu/konflikcie. Po próbie podglądu baza jest zawsze czyszczona w finally. UI otrzymuje jedynie niewielki raport liczbowy, nie staging. Sprawdzenie rewizji bieżącego uchwytu bazy odrzuca wynik, jeśli aplikacja zapisała nowe dane w czasie operacji. To ochrona świeżości podglądu, nie implementacja transakcji przywracania produkcyjnego ani wielokartowej blokady restore.

Porównanie obejmuje całe live document/data/catalog, model, plany, aktywną wersję, sesje i parametry, wyniki/serie/segmenty, notatki, snapshoty, aktywacje, pełne metadata kontenera i archiwów, ich kolejność, null/puste stringi, duplikaty treści o oddzielnych ID oraz oryginalne code units.

**Wynik oznacza zgodność z odczytanym plikiem. Nie oznacza kompletności pliku względem urządzenia użytkownika.** Nie mieliśmy dostępu do jego konkretnej kopii ani profilu telefonu. Nie dodano fikcyjnej kontroli kompletności.

Szkice nie należą do formatu treningowych kopii v5. Nie odtwarzamy ich z pliku ani nie oznaczamy jako zawarte w kopii. Test Chromium tworzy rzeczywisty lokalny szkic niezapisanych wyników, a następnie porównuje wszystkie rekordy store przed/po podglądzie, zamknięciu, błędzie i anulowaniu. Potwierdza zachowanie szkicu i pozostałej lokalnej bazy, a nie jego transfer do innego urządzenia.

## Testy i ograniczenia

Nowe Node: natywny dziennik V2/TEST, pełny roundtrip w pamięci, cały model i wszystkie archiwa z fixtures; 65 MiB raw; rollback/revision/abort; limit pliku przed file.text; uszkodzona/ucięta kopia; zmieniona rewizja; dekompresja z niezgodnym rozmiarem także po przeliczeniu obu manifestów; brak ujawniania danych w błędach. Stare testy readerów nadal pokrywają bomby, ograniczenia tokenów, kompresję, SHA i błędne struktury.

Nowe Chromium: produkcyjne kontrolki na 390×844, restart offline z precache, natywny dziennik i rzeczywisty lokalny szkic, 4 MiB opaque archive, zgodność wszystkich store i brak restore, błędny plik, aktywne anulowanie podczas wstrzymanego odczytu i odrzucenie późnego wyniku. Osobny renderer old-space 128 MiB: odczyt i próbne odtworzenie 4 MiB offline. Testy korzystają wyłącznie z syntetycznych nowych profili.

Moduł preview jest w allowliście artefaktu i precache. Historyczne harnessy PWA otrzymują go jako nowy zasób bez podmiany starego kodu aplikacji i bez usuwania asercji. Pełne Node/Chromium/PWA offline/Actions i commit raportowane w PR.

Brak testu fizycznego Androida ani dowodu szczytowego RSS. Limity formatu nie są gwarancją małego RAM: istnieją pełne staging i kopie próbnej bazy. Anulowanie jest kooperacyjne, nie przerywa natychmiast synchronicznych walidatorów, structuredClone i operacji WebCrypto. Test old-space 128 MiB nie oznacza całkowitego limitu procesu ani obsługi 65 MiB pod tym ograniczeniem.

Nie zmieniono produkcyjnej IndexedDB, jej schematu ani danych, lokalnego zapisu/szkiców, historii, Google Drive, eksportów/odczytów v1–v4, v5, Matrix i treningów. Nie zaczęto Issue #61. Rzeczywisty import v5 do IndexedDB pozostaje niewdrożony i wymaga oddzielnego, zatwierdzonego etapu z zabezpieczeniem danych oraz atomowością.
