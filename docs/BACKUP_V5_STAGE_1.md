# Issue #63 — zatwierdzony etap 1

Raport historyczny: ISSUE_63_V4_LIMIT_DIAGNOSIS.md. Kierunek v5 zatwierdzony przez właściciela w rozmowie. Raport najpierw opublikowano w PR #64, bez powtarzania zakończonych pomiarów.

## Diagnostyka jako pierwszy etap

Eksporter v4 zachowuje limity, walidację i wynik. Do błędów rozmiaru dodaje etap: live-preflight, live-document, live-model, live-token, opaque-archive-token lub preimage-token (`kind=before-import`). Nie parsuje archiwów, żeby zgadywać ich znaczenie. Komunikaty zawierają limit bajtów, a dla tokena także długość code units; nie zawierają ID, treści ani checksum. Wcześniejszy komunikat pozostaje prefiksem. Nadal nie wiadomo, który etap ogranicza dane konkretnego telefonu; obecna diagnostyka pozwoli to odczytać na urządzeniu. Live ponad limitem jest osobną, bezpieczną odmową, bez pobierania częściowego pliku.

## Izolowany moduł v5

`model/backup-v5.mjs`: `exportBackupV5(completeV2Snapshot, options)` oraz `decodeBackup(text, options)`. Nie czyta bazy ani nie przywraca danych, nie korzysta z Drive. Nie jest jeszcze importowany przez aplikację ani dodany do precache. Odczyt v1–v4 deleguje bez zmian do istniejącego czytnika. Eksporter v4 pozostaje w UI; UI v5 to następny etap integracji, a nie deklarowana naprawa telefonu.

Dokument v5 ma dokładnie `{format:'pushpull-backup',version:5,payload,archives,integrity}`. `payload` jest kompletnym, samoweryfikującym się kontenerem v4 z oryginalnym live/metadata oraz archiwami technicznych fragmentów. Zewnętrzne `archives` zawiera oryginalne metadata (wszystkie pola poza raw) oraz `parts`: null dla raw:null, albo niepustą uporządkowaną tablicę indeksów fragmentów. Pusty string ma jeden pusty fragment. Globalne indeksy muszą kolejno pokrywać wszystkie fragmenty dokładnie raz; współdzielenie skompresowanych blobów nadal wykonuje B1. Archiwalne ID, kolejność i metadata pozostają oddzielne.

Writer dzieli JS raw co 128 Ki code units, bez parsowania wnętrza i bez normalizacji. Istniejące kodowanie JSON-string-UTF8 B1 zachowuje nawet samotne surogaty i parę rozdzieloną granicą. Suma części odtwarza dokładny raw. B1 sprawdza obie sumy i długości blobów; v4 kontroluje manifest wewnętrzny, a zewnętrzny kanoniczny SHA-256 obejmuje CAŁY dokument bez własnego digest, w tym payload, kolejność referencji i oryginalne metadata. Nie jest to podpis autentyczności.

Przed udostępnieniem staging: bounded parser (rozmiar/depth/tokens/duplicate keys), outer SHA, kontrola referencji i budżetu logicznego, pełny reader v4, walidacja oryginalnych metadata/unikalnych ID, konkatenacja i freeze. Eksporter sam odczytuje wynik oraz porównuje wszystkie oryginalne raw i metadata. B1 niezależnie sprawdza pełne live/data/catalog. Wszystkie mutowalne metadata przechwytywane przed await; raw są niezmiennymi stringami. Brak częściowego wyniku przy błędzie/abort.

Zachowano limity 32 MiB pliku, 64 MiB pojedynczego bloba, 128 MiB sumy rozwiniętych blobów. Także liczona z powtórzeniami suma tokenów fragmentów PLUS live nie może przekroczyć 128 MiB: deduplikacja nie omija budżetu logicznego. Liczba fragmentów <= istniejący limit blobs (1024); B1 nadal ogranicza łączną liczbę unikalnych blobów i rekordów. Nie ma arbitralnego zwiększania limitów. Niektóre poprawne duże źródła nadal zostaną odrzucone. Live pozostaje pod dotychczasową walidacją i limitem, nie jest chunkowane.

## Nowe testy (bez powtarzania dawnych benchmarków)

- Node: syntetyczny roundtrip 65 MiB archiwum + null/pusty raw/metadata/samotny surogat, pełna równość archiwów i live. Diagnostyka v4 na obniżonych limitach; checksum/referencje/brak fragmentu również po przeliczeniu outer SHA; abort przed i podczas pracy, całkowity budżet logiczny, kompatybilność v1/v4.
- Chromium offline 390×844, renderer old-space 128 MiB: dokładne odtworzenie 4 MiB i samotnego surogatu z 33 fragmentów, odrzucenie odciętego pliku. To nie jest pomiar szczytowego RSS, test 65 MiB pod 128 MiB ani test Androida.
- Dotychczasowe testy v2/v3/v4 nadal należą do regresji; wynik Node/Chromium i CI podany w PR.

Nie zmieniono IndexedDB, semantyki preimage/odzyskiwania, produkcyjnego Drive, planów, szkiców lub Matrix. Przywracanie v5 nie jest zaimplementowane. Nie ma gwarancji niskiego RAM: pozostają snapshoty, pełne stringi wynikowe i kanonizacja/hash dokumentu. Abort nie przerywa synchronicznej walidacji. Przed integracją UI i rzeczywistym Androidem potrzebny osobny odbiór; każda ewentualna zmiana storage lub odzyskiwania wymaga zatrzymania i przedstawienia konsekwencji.
