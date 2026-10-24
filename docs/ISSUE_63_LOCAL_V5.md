# Issue #63 — lokalne pobieranie v5 po PR #64

Baza: main 7509cc9. Plan nadrzędny i pełne Issue #63 przeczytano. Raport oraz izolowany v5 są już na main po PR #64. Kierunek nowego formatu został wcześniej zatwierdzony przez właściciela. Ten PR podłącza jedynie osobny, testowy eksport lokalny; nie zmienia kontraktu v4.

## Przyczyna i granica rozpoznania

v4 wymaga jednego bloba na raw. `stringBytes` mierzy rozmiar kanonicznego tokena JSON PRZED kompresją. Nawet ASCII 64 MiB wymaga dwóch dodatkowych bajtów cudzysłowów; znaki sterujące/surogaty/backslashe zwiększają ten narzut. Historyczne zagnieżdżenia go potęgują. Ten sam komunikat może pochodzić z live albo z archiwum. Bez licznika z konkretnego telefonu nie można uczciwie przypisać jego błędu do jednego z tych źródeł. Diagnostyka main z PR #64 pokazuje już etapy bez treści/ID.

Nie ma bezstratnej poprawki obsługi >64 MiB raw w niezmienionym v4: reader również odrzuci taki blob. Kompresowanie mocniej, pominięcie preflight czy ciche zwiększenie limitów nie rozwiązuje kontraktu. Zatwierdzone v5 dzieli raw i zachowuje manifest, metadata, kolejność i dokładne code units. Odczyt v1–v4 pozostaje niezmieniony.

## Zmiana

Osobny przycisk „Pobierz kopię v5 (testowo)” obok dotychczasowego v4. Pełny snapshot istniejącej bazy przekazywany do samoweryfikującego writer v5, kontrola rewizji przed downloadem, osobna nazwa pliku. Stan i liczniki pokazują rzeczywisty format. Brak cichego fallbacku lub automatycznej zamiany v4 na v5. Moduł v5 jest teraz w allowliście i precache, więc przycisk działa offline po restarcie.

Dla starszego model bridge bez trainingJournal adapter odmawia, ponieważ pełne metadane modelu nie mieszczą się w snapshot v2. Nie eksportuje niepełnego źródła i nie tworzy wielkiego monolitycznego v3. Obsługa tego wariantu wymaga oddzielnego adaptera, bez zmiany storage; nie ogłaszamy jej jako działającej. Wariant legacy bez bridge i natywne snapshoty są obsługiwane.

Żadne dane ani archiwa nie są kasowane. Nie zmieniono IndexedDB, preimage, semantyki odzyskiwania, produkcyjnego Drive, szkiców, planów, UI Matrix lub starego eksportu/importu. Brak przywracania v4/v5 i Issue #61. Nie zmieniono limitów. Przekroczenie live lub całkowitego budżetu nadal bezpiecznie odmawia eksportu.

## Walidacja

Nowy test rzeczywistego przycisku: syntetyczne archiwum 65 MiB w IndexedDB + null, offline po przeładowaniu, 390×844, dwa pobrania, pełna zgodność danych/archiwów i wszystkich rekordów store przed/po. Testuje integrację, nie powtarza starego pomiaru v4. Test adaptera potwierdza odmowę niepełnego bridge. Historyczne harnessy PWA otrzymują nowy moduł jako nieużywany przez stare wersje zasób, z zachowaniem ich oryginalnego kodu aplikacji i wszystkich asercji.

Pełne Node/Chromium, świeżość SW, build i CI: wyniki w PR. Test viewport nie zastępuje fizycznego Androida. Dane powtarzalne syntetycznie nie dowodzą współczynnika kompresji ani budżetu RAM rzeczywistej bazy. Pełne stringi i snapshoty nadal wymagają pamięci; nie jest to lazy storage. Bez dostępu do danych właściciela nie deklarujemy, że eksport jego konkretnej bazy zmieści się w limitach.
