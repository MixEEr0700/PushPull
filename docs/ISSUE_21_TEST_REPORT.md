# Issue #21 — raport weryfikacji

Data: 22.10.2026. Punkt wyjścia: `main` `ade2a2c` (po PR #19). Gałąź `feature/issue-21-plan-import`. [Format i instrukcja](PLAN_IMPORT_ISSUE_21.md).

## Synchronizacja istniejącego PR #24 — 23.10.2026

Do gałęzi `feature/issue-21-plan-import` dołączono `main` `ef0dec6`, zachowując wcześniejsze commity importu. Rozwiązano konflikty w `app.js` (jednostki/wersje z importu oraz ręczny panel Drive z main), `tests/test_pwa.py` (oba zestawy testów) oraz wygenerowanym `sw.js`. Usunięto z `commitPlan` pozostałe wywołanie dawnej kolejki. Nie przepisano modułu `model/plan-import.mjs` ani nie zmieniono obu modułów Drive względem aktualnego main. Nowy zatwierdzony dokument kierunku i późniejsza dokumentacja main są zachowane bez zmian.

Dodatkowy scenariusz Chromium sprawdza aktywny V2 z wynikiem i szkicem: podgląd/zapis V3 nie zmienia aktywnego V2, anulowanie aktywacji nie zmienia bazy, świadoma aktywacja V3 dotyczy przyszłych treningów, bieżące sesje/ID/snapshoty/wyniki/szkice pozostają, ręczne kopie Drive i pobranie pełnego JSON zachowują plany oraz historię. Import ani aktywacja nie wykonują automatycznego POST. Test PWA importu aktualizuje teraz rzeczywisty pakiet `ef0dec6` (z ręcznymi kopiami), bez resetu danych, i wykonuje import/trening offline. Zachowano także test aktualizacji z dawnym konfliktem Drive z main; brakujący w starszych pakietach, nieużywany tam moduł importu dołączamy do technicznej allowlisty testowego buildu.

Wyniki końcowej pełnej regresji i GitHub Actions są w [PR #24](https://github.com/MixEEr0700/PushPull/pull/24); wcześniejsze liczby poniżej pozostają historią pierwszego przebiegu. Nie wykonano testu fizycznego Androida ani prawdziwego Google. Nie zmieniano danych właściciela. Issue #29/#30, nowy ekran planów i tygodniowe statystyki nie są częścią tej synchronizacji.

## Historyczna weryfikacja przed synchronizacją z main (22.10.2026)

| Weryfikacja | Wynik |
| --- | --- |
| `node --test tests/*.test.*` | 85/85 PASS |
| `python3 -m unittest discover -s tests -p 'test_*.py' -v` | 73/73 PASS, Chromium z istniejącego Playwright |
| `node --check` dla app/storage/indexeddb/sw | PASS |
| `python3 scripts/build_release.py --check` | PASS — worker odpowiada wszystkim zasobom |
| `python3 scripts/build_release.py --output /tmp/pushpull-issue21-final` | PASS — lokalny artefakt, bez publikacji |
| `git diff --check` | PASS |

Nowe testy wykorzystują `tests/fixtures/plan-v3.json` i syntetyczną kolejną wersję V4. Nie używano pamięci telefonu ani danych właściciela. Dotychczasowe testy V2 pozostają regresją w izolowanych profilach testowych.

Sprawdzono:

- Walidację formatu, referencji, ID, zakresów, stron, nieokreślonych celów; odrzucenie nieobsługiwanego protokołu, niepełnego pliku, duplikatów JSON i kolizji niezmiennych ID. Błąd nie modyfikuje źródła.
- Podgląd/anulowanie, osobny zapis nieaktywnego planu, anulowanie oraz świadomą aktywację V3 i V4. Nowa wersja nie zmienia starej sesji, wyników, snapshotu ani szkicu; zakończenie starej sesji nie przesuwa nowej rotacji.
- Dowolne jednostki, niezależne 1A/1B/1C, różne cele, back-off, segmenty dropsetu i L/P. Zmiana maszyny wymaga osobnego wariantu, zamiana osobnej tożsamości. Przeniesienie tej samej tożsamości do innej jednostki zachowuje zgodność pełnej kopii.
- Import przerwany przez abort transakcji IndexedDB i ponowienie bez częściowych planów/duplikatów. Historia i aktywna sesja zachowane, komunikat sukcesu dopiero po zakończeniu zapisu.
- Nowy trening → szkic dropsetu → reload → odzyskanie wszystkich segmentów → zapis; L/P; edycja segmentu w kalendarzu bez zmiany snapshotu, statystyki, pełna kopia v3 i odtworzenie w osobnym profilu. Zapis A nie usuwa szkicu B.
- Rzeczywisty worker: aplikacja z kodem aktualnego `main` → aktualizacja PWA bez czyszczenia danych → offline → import/aktywacja syntetycznego planu → odzyskanie starego szkicu → przyszły trening → restart → odzyskanie szkicu i zapis segmentów.
- Dotychczasową regresję migracji, offline, aktualizacji/cache, odmowy/quota/przerwań, wielu kart, szkiców, kalendarza, tonażu, historii i backupów.
- Istniejący Drive z symulowanym Google: kolejki, retry, konflikty i odtwarzanie; dodatkowo pełna kopia v3 zawiera importowane plany i przywraca je bez zmiany danych/konfiguracji konta. Nie zmieniono modułów ani protokołu Drive.
- Istniejące porównanie mobilnego Matrix z zatwierdzonym wzorcem; nie dodano masek. CSS, HTML bazowy, manifest/tożsamość PWA, ikony, dane wbudowanego V2 i oba moduły Drive są identyczne z `main`.

Historyczne testy porównujące cały `storage.js` bajt po bajcie z etapem 3/A/B dostosowano, ponieważ walidacja musi teraz akceptować zadeklarowane jednostki i relacje natywnych snapshotów. Zachowano testy zgodności interfejsu, tożsamości PWA i rzeczywistej walidacji/ochrony historii. Nie dodano frameworka ani workflow CI. Dotychczasowy GitHub Actions uruchamia powyższą regresję; aktualne wyniki są w Checks powiązanego PR.

## Niewykonane i ograniczenia

- **Fizyczny Android: niewykonane**, brak rzeczywistego urządzenia. Chromium z mobilnym viewportem nie zastępuje testu na telefonie. Lista odbioru syntetycznego planu jest w instrukcji.
- **Prawdziwe konto Google/OAuth: niewykonane**. Obecna regresja używa ręcznych kopii Drive z Issue #26; mock nie potwierdza konfiguracji konta ani odnowienia tokenu na Androidzie.
- Nie importowano rzeczywistego nowego planu i nie aktywowano planu na urządzeniu właściciela. Brak ręcznego wdrożenia i automatycznego scalenia.
- Import ogranicza się do istniejącego protokołu wyników: kg/null, zmienne segmenty bez osobnych celów segmentów, całościowe L/P, kolejne niezależne karty grupy. Nieznane mechaniki wymagają implementacji, zamiast cichej akceptacji opisu. Szczegółowe ograniczenia w kontrakcie pliku.
- Plik planu nie jest kopią historii ani szkiców. Dotychczasowe szkice pozostają lokalnie; ich utrata po usunięciu danych przeglądarki nie jest rozwiązywana przez import planu. Należy zachowywać pełne kopie poza telefonem.
