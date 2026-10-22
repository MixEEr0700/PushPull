# Issue #21 — raport weryfikacji

Data: 22.10.2026. Punkt wyjścia: `main` `ade2a2c` (po PR #19). Gałąź `feature/issue-21-plan-import`. [Format i instrukcja](PLAN_IMPORT_ISSUE_21.md).

## Końcowa weryfikacja lokalna

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
- **Prawdziwe konto Google/OAuth: niewykonane**. Mock potwierdza zgodność z istniejącą synchronizacją, nie konfigurację konta ani odnowienie tokenu na Androidzie.
- Nie importowano rzeczywistego nowego planu i nie aktywowano planu na urządzeniu właściciela. Brak ręcznego wdrożenia i automatycznego scalenia.
- Import ogranicza się do istniejącego protokołu wyników: kg/null, zmienne segmenty bez osobnych celów segmentów, całościowe L/P, kolejne niezależne karty grupy. Nieznane mechaniki wymagają implementacji, zamiast cichej akceptacji opisu. Szczegółowe ograniczenia w kontrakcie pliku.
- Plik planu nie jest kopią historii ani szkiców. Dotychczasowe szkice pozostają lokalnie; ich utrata po usunięciu danych przeglądarki nie jest rozwiązywana przez import planu. Należy zachowywać pełne kopie poza telefonem.
