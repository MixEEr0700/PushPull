# Issue #63 — diagnoza i projekt do zatwierdzenia

Baza: `main` `7feec55` (po PR #62). Ten PR jest diagnostyczny: nie naprawia jeszcze eksportu danych telefonu i nie zmienia formatu ani kodu produkcyjnego.

## Udowodnione

`tests/v4-limit-probe.mjs` tworzy wyłącznie syntetyczne kopie, bez otwierania bazy i bez plików użytkownika. Osobno umieszcza duży tekst w rozszerzeniu live, opaque recovery archive oraz w dwukrotnie zagnieżdżonym historycznym raw. Każdy scenariusz wywołuje prawdziwy eksporter B1 i sprawdza odrzucenie oraz zachowanie oryginalnego stringa. Wyjście zawiera tylko etykietę syntetycznego scenariusza, liczniki bajtów/code units, czas i rezultat.

String ASCII długości 67 108 864 code units zajmuje jako token JSON 67 108 866 bajtów: cudzysłowy też należą do tokena. Limit pojedynczego rozwiniętego bloba wynosi 67 108 864 bajty. Kompresja następuje dopiero po kontroli limitu i nie może go obejść.

- Live: `detach()` → `jsonBytes(liveSource, decodedBlobBytes)` → `stringBytes`. Również sumaryczny live oraz jego opakowanie v3/token mogą osiągnąć limit w późniejszym serialize/add(live).
- Archiwum: `add(raw)` → `stringBytes(raw, decodedBlobBytes)` przed encode/compress. Zagnieżdżone historyczne JSON pozostaje opaque; backslashe i cudzysłowy zwiększają rozmiar zewnętrznego tokena, bez związku z liczbą treningów.
- Czytnik A niezależnie odrzuca descriptor bloba ponad 64 MiB, kontroluje rzeczywiście rozwinięte bajty oraz parsowanie tokena. Samo pominięcie preflight eksportera nie jest naprawą.

**Nie ustalono, który wariant wystąpił na telefonie właściciela.** Brak dostępu do jego danych i liczników rozmiaru na tym urządzeniu. Oba źródła generują identyczny komunikat. Hipoteza o preimage jest wiarygodna, ale nie jest rozpoznaniem realnej bazy. Nie należy prosić o wysłanie całej kopii w celu rozpoznania.

## Najmniejsza bezpieczna poprawka w obecnym kontrakcie — projekt

Rozdzielić odmowę na etapy: live-preflight, live-document, live-token, archive-token. Do komunikatu dodać wyłącznie etap, limit i licznik rozmiaru (bez ID, nazw, indeksów, checksum i treści). Nie zmieniać danych ani pobierać częściowej kopii. Pomiar długości powinien liczyć bajty bez alokowania pełnego escapowanego tokena. Pozwoli to rozpoznać telefon, lecz **nie umożliwi eksportu ponadlimitowej kopii**. Ten PR nie wdraża jeszcze tej telemetrii.

## Proponowane rozwiązanie archiwów — wymaga zatwierdzenia

Nie rozszerzać po cichu v4: jego kontrakt wymaga pojedynczego `blobId` dla każdego raw. Proponowany nowy **format v5**, obok niezmienionego czytnika i eksportera v4:

1. Archiwum zachowuje wszystkie metadata, kolejność i odrębne ID. Zamiast pojedynczego blobId ma uporządkowane `parts` referujące skompresowane bloby; null pozostaje jawnie inną wartością niż pusty tekst. Nie parsować wnętrza raw.
2. Dzielić oryginalny JS string po granicach code units (docelowo 128 Ki code units na fragment). Każdy fragment kodować istniejącym kanonicznym JSON-string-UTF8: zachowa także samotne surogaty, NUL i pary przecięte granicą. Po walidacji konkatenacja odtwarza dokładnie oryginalny ciąg jednostek kodowych.
3. Każdy fragment zachowuje obie sumy SHA-256, rozmiary i limit dekompresji. Kanoniczny SHA manifestu chroni uporządkowaną listę referencji i metadata. Zmiana kolejności/usunięcie/podmiana fragmentu musi zostać wykryta. Deduplicacja fragmentów nie usuwa ani nie scala rekordów archiwum.
4. Zachować limit pliku 32 MiB, pojedynczego bloba 64 MiB i sumy unikalnych rozwiniętych blobów 128 MiB. Liczyć narzut tokenów fragmentów do budżetu. Dodać osobny ograniczony budżet referencji i łącznej logicznej długości odtwarzanych raw, bo współdzielenie fragmentów może powielić wynik. Konkretne wartości tego nowego budżetu wymagają decyzji i pomiarów, nie cichego wdrożenia.
5. Nie zmieniać live w tej pierwszej wersji projektu: live ponad obecnym limitem nadal bezpiecznie odrzucać. Jeśli telefon ogranicza live, samo chunkowanie archiwów go nie naprawi; potrzebny osobny projekt strumieniowego modelu/walidatora. Także archiwum powyżej całkowitego budżetu wymaga innego rozwiązania, nie obietnicy obsługi dowolnej wielkości.
6. Odczyt istniejących v1–v4 pozostaje niezmieniony. Stare aplikacje jawnie odrzucą v5. Nie migrować IndexedDB ani dawnych plików. Nowy plik samodzielny. Brak podłączenia do restore/Drive i brak Issue #61. Przyszła pełna walidacja przed ekspozycją staging, błędy/abort bez częściowego wyniku.

Fragmenty nie gwarantują małego RAM: końcowe stringi i snapshoty nadal mogą być duże. Przed wdrożeniem trzeba zmierzyć szczyt pamięci, rozważyć odczyt do pliku/staging i sprawdzić fizyczny Android. Nie implementować własnego kryptograficznego hashera w celu obejścia alokacji.

## Walidacja i granice

Nowe testy Node i Chromium odtwarzają rzeczywisty limit 64 MiB dla live/opaque/nested-archive. Chromium dodatkowo uruchamia te scenariusze offline przy viewport 390×844, a w osobnym rendererze z old-space 128 MiB używa obniżonego limitu 1 MiB. Ten ostatni test sprawdza bezpieczną odmowę pod ograniczeniem, NIE obsługę 64 MiB ani całkowity limit RAM Androida.

Nie ma nowego eksportera v5, więc nie ma dowodu roundtrip nowego formatu i PR nie ogłasza bezstratnej naprawy. Produkcyjne pliki, limity, kopie, szkice, Drive, IndexedDB, plany i Matrix nie są modyfikowane. Wyniki poleceń i CI są w opisie PR. Do dalszej implementacji potrzebna akceptacja zakresu diagnostyki i projektu nowego kontraktu.
