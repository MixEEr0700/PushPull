# Compact Matrix v0.4 — Issue #95

Baza: `main` / `a476094` (scalone PR #92 i #93). Rozwinięcie istniejącego UI zgodnie z Issue #95; bez Issue #94.

## Zmiany

- Numer 20 px, nazwa 18 px. Parametry i rzeczywisty ostatni wynik widoczne także po zwinięciu. Np. `3 × 8–10 | tempo 2111 | RIR 0`; odrębne cele, back-off, drop i nieokreślone wartości pozostają jawne. Nie zmieniono danych planów/snapshotów ani nazw zapisanych ćwiczeń.
- Wynik skracany tylko wtedy, gdy wszystkie wartości i znaczenia serii są jednakowe. Przy 10/10/9 (również przy jednakowym kg) pokazane są wszystkie trzy wartości w kolejności. Zachowano parowanie L/P według referencji, informację o asymetrii/brakującej parze, segmenty, back-off i rundy. Symetryczne L/P są teraz jawnie oznaczone również w skrócie. Prezentacja nie zmienia rekordów ani tonażu.
- Jedna sekcja „Notatki” wewnątrz rozwiniętej karty. Źródłowy tekst wyświetlany bezpośrednio, tylko do odczytu; mała proweniencja „Trener” / źródło mieszane / historyczny autor nieustalony. Brak etykiet „Wskazówki źródłowe” i „Moja notatka” w widoku. Ołówek otwiera wyłącznie notatkę użytkownika, plus służy do jej dodania. Nie rozdzielamy ręcznie mieszanych tekstów C1/C2/D2 ani nie przypisujemy ich trenerowi.
- Dwa szybkie pola: powtórzenia, kg, bez widocznych nagłówków, z nazwami dostępnymi dla czytników. Zapis i edycja serii obok siebie. Brak powtórzonej nazwy ćwiczenia i nadmiarowych nagłówków. Historia/statystyki i korekta po potwierdzonym zapisie pozostają dostępne.
- Pola szybkie prezentują pierwszą rzeczywistą parę z edytowanego wyniku, szkicu lub porównywalnego poprzedniego wyniku. Nie sprowadzają całego wyniku do pierwszej pary. Sam zapis bez zmiany pól zachowuje 10/10/9. W nowej sesji zachowujemy też poprzednie dodane/usunięte wiersze i segmenty, nadając nowe ID wynikom; korekta i wznowiony szkic zachowują własne ID. Nie stosujemy poprzedniego wyniku z obcego planu/wariantu lub jawnie innej konwencji kg.
- Szybka zmiana nadal dotyczy głównych segmentów bieżących serii i wymaga potwierdzenia, jeśli zastępuje indywidualne wpisy. Zmiana samego kg nie znosi ochrony różnych powtórzeń. Segmenty drop nie są zastępowane wspólnym polem. Zwijanie edytora nie kasuje jego danych.
- Indywidualne wiersze mają numer, powtórzenia, kg i usuwanie; pozostają dodawanie, semantyczne etykiety oraz niezbędne kontrolki L/P/drop/grup.
- Naprawiono potwierdzony błąd przechwytywania szkicu po dodaniu/usunięciu serii: przebudowa wierszy odłączała kliknięty element od formularza przed późniejszym handlerem. Teraz zachowujemy referencję formularza przed zmianą DOM i przechwytujemy nowy stan przez istniejące API szkiców. Dotyczy to obu formularzy; bez nowych pól/protokołów i bez zatwierdzania wyniku. Test usunięcia bez kolejnego znaku był RED przed poprawką i PASS po niej. Dodanie pustej serii także przetrwało restart.
- Lokalne SVG nad etykietami nawigacji: hantel, kalendarz, baza danych. Bez zależności od fontów/sieci i bez zmiany tras lub zawartości Dane.

## Zachowane mechanizmy

Bez zmian w modułach IndexedDB v2, protokole zapisu, CAS, walidacji, readback, `strict complete`, indeksach, konwersji, statystykach, rotacji, modelach planów, kodekach backupów v1–v6, przywracaniu i Drive. Nie zmieniono schematu ani migracji; nie usunięto danych użytkownika i nie opublikowano wersji produkcyjnej. Nawigacja do Dane nie wywołuje `ensureFull()`.

Szkic rozpoczętej edycji w pamięci ma pierwszeństwo przed ponownym pobraniem poprzedniego wyniku. Po restarcie zachowano dotychczasowe świadome „Wznów szkic” i kontrolę zgodności/konfliktów; nie wybiera się zwycięskiej wersji z wielu kart. Lokalne szkice samych notatek nadal mają ograniczenia udokumentowane w raporcie F (osobne pobranie, brak integracji z istniejącymi formatami kopii).

## Weryfikacja

- Node: **219/219 PASS** (pełny zestaw), w tym nowe testy 10/10/9, pojedynczych/identycznych/różnych serii, L/P, zmienionych kontekstów, segmentów drop, bezmutacyjnego formatowania i ID nowych wyników.
- Nowe scenariusze Chromium: 10/10/9 → kolejny trening → restart/wznowienie szkicu → dodanie/usunięcie → ponowny zapis bez rozwinięcia; ochrona osobno kg i powtórzeń; 360/390/412 px, długie teksty Unicode, aria-label, czytelność źródeł, przyciski obok siebie i ikony. Końcowy moduł: 6/6 PASS, w tym strukturalne zmiany bez kolejnego znaku i restart.
- Zachowane 4 testy notatek (kolizje zakresu, dwa źródła, quota/retry, restart/anulowanie) PASS; 4 testy treningu V2 (back-off, drop, L/P, grupy, historia/statystyki/restore i abort/retry) PASS; 3 testy prezentacji planu/aktywacji PASS.
- Build produkcyjny i zgodność worker/hash PASS. Pełny lokalny przebieg objął 203 przypadki: 197 PASS; sześć nieaktualnych oczekiwań testowych (dwa założenia nowego scenariusza, cztery stare formaty prezentacji PWA) poprawiono i powtórzono z wynikiem PASS. Wszystkie asercje integralności pozostały. Cztery dotknięte scenariusze PWA ponownie PASS; końcowy moduł nowych testów 6/6 PASS. Pełny workflow PR weryfikuje razem końcowe 206 przypadków Chromium/PWA oraz 219 Node; jego finalny wynik jest podany w PR.

Testy poprzednich interfejsów mają wspólny helper otwierający wynik: aktualny formularz pojawia się automatycznie, w starszych wydaniach i podczas korekty używany jest dotychczasowy przycisk. Asercje danych/bezpieczeństwa nie zostały usunięte ani osłabione.

## Ograniczenia i odbiór

Testy oraz benchmarki tej zmiany są syntetyczne, na Chromium/Linux, z izolowanymi bazami; nie są nowym testem fizycznego Pixela 9 ani prawdziwego konta Google. Na telefonie do odbioru: czytelność nagłówków i źródeł, klawiatura, tap-targety, 10/10/9, przejście do indywidualnej edycji, wznowienie szkicu i zapis po aktualizacji. Nie zadeklarowano ponownego odbioru sprzętowego.

Jeden PR do przeglądu, bez samodzielnego scalania i wdrożenia.

## Pomiary przed/po

Chromium/Linux, CPU ×4, oddzielnie od testów, izolowane profile. Przed: zachowane pomiary G, których SHA-256 runtime jest identyczne z bazowym `main`; po: końcowy runtime tej zmiany. Użyto dokładnie tych samych zachowanych fixture’ów A–E. Nie powtarzano pomiarów bazowych ani generowania danych. Zmieniono jedynie otwieranie formularza w benchmarku tak, by obsługiwało automatycznie widoczny edytor; zegar/probe `strict complete` bez zmian. Orakle zachowania źródłowej historii/archiwów PASS. [Dane zagregowane i hashe](performance/compact-matrix-95.json).

| Baza | strict complete przed mediana / p95 | po mediana / p95 | próbkowany JS heap max przed / po |
| --- | --- | --- | --- |
| 4 sesje | 141 / 289 ms | 125 / 221 ms | 12.4 / 12.5 MiB |
| 40 sesji + raw 4 MiB i zachowane checkpointy | 187 / 312 ms | 195 / 318 ms | 22.7 / 22.2 MiB |

Każdy przypadek: 8 zapisów (4 nowe + 4 korekty). Przy n=8 p95 jest maksimum próby; niewielkie różnice nie są dowodem poprawy/regresji na telefonie. Zegar zaczyna się przy kliknięciu, kończy w pierwszym natywnym handlerze transakcji `strict complete`, wraz z osobno zachowanym `event.timeStamp`. To nie czas pokazania toastu. Próbkowany heap nie oznacza całkowitego RAM ani gwarantowanego szczytu.

| Wejście do Dane, offline (n=5) | przed mediana / p95 | po mediana / p95 | żądania IDB po wejściu |
| --- | --- | --- | --- |
| 4 sesje | 21 / 43 ms | 26 / 57 ms | 0 |
| 40 sesji + raw 4 MiB | 32 / 50 ms | 29 / 47 ms | 0 |
| 400 sesji + raw 4 MiB | 31 / 48 ms | 33 / 53 ms | 0 |

Brak pełnego audytu przy nawigacji. Pomiary potwierdzają zachowanie szybkiej ścieżki na syntetykach, nie odbiór fizycznego Androida.
