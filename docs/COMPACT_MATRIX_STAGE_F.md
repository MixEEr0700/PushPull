# Etap F — Compact Matrix v0.4 (Issue #43)

Baza: `main` / `58310ff2a39619d966e11bdb742e2a8050133ca3` (PR #91).
Zakres zatwierdzony przez właściciela: zmiana istniejącego UI, bez przebudowy aplikacji.

## Zmiany

- Czarne tło, karty #111, jasny tekst i ograniczony akcent #39FF74.
- Zwinięta karta: numer, nazwa, chevron. Po otwarciu: parametry oddzielone `|`, ostatni wynik (powtórzenia × kg, serie oddzielone `|`, faktyczny wiek kontekstu), źródłowe wskazówki, moja notatka i dotychczasowy formularz wyników.
- Formularz dostępny od razu po otwarciu ćwiczenia w sesji; powtórzenia przed kg, także w indywidualnych seriach. Po potwierdzonym zapisie znika; przycisk korekty pozostaje.
- Niezależne, tylko do odczytu wskazówki trenera. Pusta notatka użytkownika zajmuje miejsce małej ikony z plusem; zapis/anuluj, auto-wysokość i istniejący trwały zapis.
- Minimalny obszar dotykowy przycisków/pól 44 px; wynik zawija się bez poziomego przewijania.

## Integralność i ograniczenia notatek

Instrukcje o pochodzeniu `trainer` trafiają do „Wskazówek trenera”. Dzisiejszy plan zawiera również mieszane teksty C1/C2/D2 ze źródłem `owner`: pozostają w całości w osobnym bloku źródłowym. UI nie zgaduje autorstwa fragmentów ani nie zmienia planu. Historyczne teksty o nieustalonym autorze też pozostają dostępne.

Notatki V2 wykorzystują dotychczasową strukturę `userNotes`; ID nowego wpisu obejmuje wersję planu i ćwiczenie. Stare dowolne ID pozostają czytelne. Widok nie przenosi notatki z innej znanej wersji planu. Nie zmieniono schematu, kodeków ani formatów kopii. Stary UI może nie rozumieć nowego zakresu ID, choć stary czytnik nadal zachowuje wpisy.

Niezatwierdzony tekst notatki jest osobnym lokalnym szkicem UI. Każda karta przeglądarki ma własny rekord/token; przy restarcie różne źródła nie mają automatycznie wybieranego zwycięzcy. Konflikt blokuje zapis do ręcznego uzgodnienia, a przycisk pobrania zachowuje źródłowe wersje. Dopiero potwierdzony zapis lub świadome anulowanie oznacza konkretny token jako zakończony. Nie usuwa się danych innych kart. Błąd quota zapisu szkicu pokazuje ostrzeżenie i umożliwia pobranie tekstu z pamięci. Nie obiecuje to atomowego snapshotu wszystkich kart.

**Lokalny szkic notatki nie został dodany do istniejących formatów backupu ani kolektora szkiców treningowych.** UI wyraźnie informuje o tym ograniczeniu; istnieje osobne pobranie szkicu. Zatwierdzone notatki są normalną częścią danych. Surowe rekordy zakończonych szkiców są zachowane; zapełnienie localStorage może wymagać pobrania szkicu. Żadnego resetu/GC danych użytkownika.

## Zachowane mechanizmy

Bez zmian w IndexedDB v2, indeksach i protokole zapisu przyrostowego, CAS, walidacji, readback i zdarzeniu `strict complete`. Zachowane szkice wyników, daty/rotacja, korekty historii, serie indywidualne, L/P, back-off/drop, ćwiczenia łączone, tonaż, statystyki i plany. Bez zmian w transportach Drive, backupach v1–v6, odtwarzaniu ani leniwym wejściu do Dane z PR #91.

## Weryfikacja

Wyniki lokalnej regresji i pomiarów poniżej. Testy zamrożonego HEAD są również wykonywane przez standardowy workflow PR. Dawne asercje identycznych bajtów CSS v0.3 zastąpiono kontraktem zatwierdzonego v0.4; asercje danych, PWA identity/ikon i importów bez efektów ubocznych pozostają.

- Pełna lokalna regresja Chromium/PWA: 195 testów, 193 PASS i dwa stare oczekiwania wyglądu opisane wyżej; po dostosowaniu układu 10 testów docelowych PASS (w tym oba przypadki). Asercje danych nie zostały osłabione.
- Nowe scenariusze: treść notatki po zwinięciu/reload, quota i retry bez utraty tekstu, druga edycja/anulowanie, dwa rozbieżne źródła, pochodzenie trenera i jego pusty blok; układ mobilny 360/390/412 px. Pełne scenariusze: indywidualne serie, L/P, back-off/drop/grupy, historie, CAS/abort/quota, backup/restore, offline, restart i aktualizacja PWA.
- Ostateczny pełny Node: **211/211 PASS**; build produkcyjny i zgodność worker/hash PASS; zamrożony HEAD przechodzi pełny workflow (Node + Chromium/PWA).

Pomiar seryjny na dokładnie tych samych zachowanych syntetycznych fixture’ach A–E; po jednym izolowanym profilu i 8 zapisów na wariant (4 nowe i 4 korekty). p95 przy n=8 jest maksimum, nie wiarygodnym oszacowaniem ogona dla telefonu. Źródłowe historie/archiwa sprawdzone przez orakle benchmarku. Dane zagregowane: [compact-matrix-f.json](performance/compact-matrix-f.json).

| Baza | strict complete przed mediana / p95 | po mediana / p95 | próbkowany heap zapisu przed / po |
| --- | --- | --- | --- |
| 4 sesje | 148 / 206 ms | 155 / 253 ms | 12,6 / 12,3 MiB |
| 40 sesji + raw 4 MiB (z zachowanymi checkpointami) | 195 / 341 ms | 182 / 301 ms | 22,4 / 20,4 MiB |

Pomiar nie wykazuje wielosekundowego zapisu. Niewielkich różnic nie interpretujemy jako istotnej poprawy/regresji na podstawie n=8. UI nie zmienia protokołu zapisu. Heap to próbkowany JS heap, nie całkowity RAM ani gwarantowany szczyt.

| Wejście do Dane, offline (n=5) | przed mediana / p95 | po mediana / p95 |
| --- | --- | --- |
| 4 sesje | 31 / 42 ms | 33 / 60 ms |
| 40 sesji + raw 4 MiB | 36 / 62 ms | 27 / 58 ms |
| 400 sesji + raw 4 MiB | 28 / 45 ms | 33 / 49 ms |

W każdej próbie wejścia: **0 żądań IndexedDB**, brak pełnego audytu historii/archiwów. Pomiar `scripts/measure_compact_navigation.py` nie wykonuje kosztownego eksportu w pętli; pełną integralność eksportów sprawdza regresja.


## Odbiór na telefonie

Pomiary są syntetyczne (Chromium/Linux, CPU ×4), nie są pomiarem Pixela 9. Na fizycznym Androidzie należy ocenić układ przy klawiaturze, przewijanie, otwarcie karty, notatki, serie specjalne i rzeczywisty czas zapisu. Nie zadeklarowano odbioru urządzenia ani osiągnięcia celu czasu na telefonie.
