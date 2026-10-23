# Issue #34 — powrót do wersji i ciągłość statystyk

Doprecyzowanie po PR #38, baza `3a92fbf`. Obowiązuje najnowsza zatwierdzona decyzja w [kierunku planów/statystyk](PLANY_I_STATYSTYKI_KIERUNEK_2026-10-23.md). Wcześniejsze okresy tej samej wersji pozostają wspólną historią; nowy okres rotacji nie jest nową wersją ani resetem wyników.

## Diagnoza i zmiany

- Pusty wybór na telefonie z samym V2 i starym szkieletem nie dowodzi utraty planu. Szkielet zawiera niepełne/niezweryfikowane definicje; nie wolno utworzyć z niego fikcyjnej V1. Komunikat wyjaśnia teraz tę sytuację oraz potrzebę jednorazowego importu kompletnego, zatwierdzonego planu.
- Wcześniej obca wersja wymagała również wpisu `importedPlans`, mimo zachowania pełnej definicji. `storedPlanModel` wspólnie dla listy i aktywacji sprawdza rzeczywisty rejestr, snapshoty i zachowane pakiety. Wymaga kompletności wszystkich jednostek, poprawnych relacji i obsługi danego protokołu serii. Jawnie nieokreślone parametry pozostają dozwolone, zgodnie z dotychczasowym modelem.
- Aktywacja bez reimportu dołącza wyłącznie brakujące oryginalne definicje/ID. Nie zmienia istniejących definicji o tym samym ID; konflikt, niepełność, obcy właściciel lub nieobsługiwany protokół blokuje aktywację. Nie rekonstruuje zatwierdzenia, dat ani zaleceń. Sam podgląd/lista nie zapisuje danych. Stosuje dotychczasową pełną kopię sprzed zmiany i atomowy commit.
- Potwierdzenie mówi o nowym okresie, pierwszej jednostce i kontynuacji statystyk. Pozostaje ochrona otwartej sesji, snapshotu/szkiców i rotacji; ta sama wersja już aktywna nie tworzy zdublowanej aktywacji.
- Karta powracającej wersji pokazuje jej ostatni rzeczywisty wynik w dotychczas zgodnym kontekście. Wynik innej wersji nie zastępuje go. Domyślny filtr statystyk ćwiczenia odpowiada wersji karty i obejmuje wszystkie jej okresy; istniejący jawny wybór całej historii wariantu pozostaje dostępny.

## Minimalna korekta wykresów

`weeklyStats` już agregował V2-A i V2-C razem: nie zmieniono algorytmu sum, liczby serii, tonażu ani kalendarza ISO. Puste tygodnie pozostają zerami w tabeli, w swoich rzeczywistych miejscach osi czasu; linia wykresu jest przez nie przerwana. Nie interpolujemy aktywności V2 w czasie V3.

Istniejący wykres ćwiczenia korzysta teraz z odległości pomiędzy datami sesji, zamiast równych odstępów „trening 1, 2”. Linia jest przerwana przez brakujący tydzień ISO, zmianę wersji lub wiarygodnie zarejestrowaną aktywację innego planu pomiędzy snapshotami. Pierwsza i ostatnia etykieta to daty. Nie dopisuje to obserwacji ani dat aktywacji; daty sesji pozostają datami sesji. Historyczne znaczniki techniki zachowano. Bez nowego wykresu, kontrolek graficznych, CSS lub zmian nawigacji.

## Weryfikacja i ograniczenia

- Node: rejestr bez pliku importu, kompletna wersja tylko w snapshotach/pakiecie, odrzucenie szkieletu/niepełnej definicji/kolizji, V2-A + V2-C, puste tygodnie i proporcjonalna oś czasu z przerwą. Kontrola braku mutacji odczytu.
- Chromium: aktywacja wersji tylko ze snapshotu przy zachowaniu otwartej sesji i szkicu; podgląd/anulowanie bez zapisu.
- PWA: rzeczywisty update service workera z `3a92fbf`, V2 w lutym → V3 → powrót V2 w sierpniu offline; pełna równość bazy i szkiców po aktualizacji, wznowienie starego treningu, ostatni wynik V2 105 kg i kolejny 95 kg, trzy wyniki w jednej historii/statystyce V2, 9000 kg wspólnego tonażu, puste tygodnie i przerwane linie, dwa rzeczywiste okresy, pełny JSON i odtworzenie na pustym profilu, restart offline. Dane i aktywacje wyłącznie syntetyczne.
- Pełna regresja Node/Chromium oraz CI: faktyczne wyniki w raporcie PR.

Brak pełnej wersji nie jest naprawiany zgadywaniem. Brak dawnych timestampów nadal oznacza nieustalone okresy. Nie testowano fizycznego Androida ani rzeczywistego konta Google; odbiór użyteczności na telefonie pozostaje do wykonania przez właściciela. Bez migracji bazy, zmiany wyników, snapshotów, szkiców, notatek, ręcznych kopii Drive i kodu dopisku z Issue #36. Bez ingerencji w dane właściciela, ręcznego wdrożenia i automatycznego scalenia.
