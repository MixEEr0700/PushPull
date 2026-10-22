# Etap 5B / krok A — raport testów

Baza `012fe5a8d2da4107dea5a01f27c4faffec544430` (main po PR #5), gałąź `feature/stage-5b-a-data-model`. Implementacja wyłącznie niezależnych kontraktów w `model/training-model.mjs`. Brak integracji ze starym mechanizmem treningowym.

## Zakres testów proporcjonalny do zmiany

Dodano 12 scenariuszy Node w `tests/training-model.test.mjs`, bez frameworka/zależności. Sprawdzają walidację samodzielnych rekordów i grafu, przypadki wadliwych danych, odrębność identity/variant/position, ochronę dipów PUSH-A-4, historyczne ID, back-off, elastyczne drop, grupę dwóch ćwiczeń/rund, strony/konwencje, nieokreślone cele, notatki/pochodzenie, snapshot po późniejszej zmianie planu, powiązania rezultatów/właściciela oraz JSON round-trip. Dziesięć wariantów D2 to fixture kontraktów, nie produkcyjny seed.

Test importu blokuje dostęp do browser/storage/network globals i sprawdza niezmienione bajty runtime względem main. Istniejący test paczki potwierdza zgodność workera i allowlisty — nowy moduł nie jest częścią wydania. Jedyna zmiana CI: komenda Node wykrywa oba pliki testów. Bez nowej infrastruktury, jobów lub usług.

## Faktyczne wykonanie lokalne — 22.10.2026

```sh
node --check model/training-model.mjs
node --check app.js
node --check indexeddb.js
node --check storage.js
node --check sw.js
node --test tests/*.test.*
python3 scripts/build_release.py --check
python3 scripts/build_release.py --output dist/stage5ba
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

- Składnia JS i nowego modułu: **PASS**.
- Node: **55/55 PASS**, 0 pominiętych — 43 dotychczasowe + 12 nowych.
- Python/Chromium: **43/43 PASS**, 0 pominiętych, 50,304 s.
- Matrix: **12/12 porównań pikseli PASS** z zatwierdzonym `92390b1`.
- Paczka/worker/hash: **PASS**. Release nadal `3421843c0714c4ba7167e377`, bez zmiany zasobów runtime i bez publikacji.
- Wykonano całą istniejącą regresję rotacji, kalendarza, serii/tonażu/statystyk, historii/notatek/techniki, migracji z błędami/quota/retry, kopii/importu, offline, restartu procesu i aktualizacji PWA.

`git diff --check` i kontrola niezmienności runtime/adapterów/ikon/szablonu workera/budowy/historycznej specyfikacji: **PASS**. Lokalne odnośniki nowych dokumentów rozwiązują się poprawnie.

GitHub Actions dla commitu tego PR jest odrębnym wykonaniem; aktualne wyniki podaje opis PR i końcowy raport zadania. Workflow nie publikuje aplikacji.

## Granice wyniku

Kontrakty są podstawą kroku B (projekt/adaptery pełnej kopii), ale ten PR ich nie implementuje. Nie wykonano migracji IDB, aktywacji, modyfikacji danych, nowego UI/edytora/copy L/P ani nowych obliczeń tonażu. Czysty snapshot jest niemutowalną, serializowalną strukturą; trwałe zapisanie go w repozytorium sesji jest dalszą pracą. Wyniki numeryczne segmentów i obsługa formularzy nie są nową gotową funkcją aplikacji.

Brak testów fizycznego Androida/WebAPK i awarii sprzętu. Testy używają własnych profili i danych syntetycznych, nie historii telefonu. O1/O2/O3 pozostają nierozstrzygnięte dla konkretnych przyszłych wariantów; model reprezentuje braki bez ich uzupełniania. Nie deklarujemy gotowości V2 do aktywacji/codziennego użycia. Nie konfigurowano hostingu, Drive/OAuth ani innych repozytoriów.
