# Dziennik funkcjonalny — pierwsza kompletna część

Baza: `main` po PR #8, `d2ba9754d92fe5885e6daa9650945551f49da69e`. Zgodnie z dopuszczonym podziałem większego zlecenia ten PR kończy się na działającym przepływie **sesja → różne serie → ponowny odczyt → korekta → pełna kopia i odtworzenie**. Nie oznacza ukończenia całego treningu V2.

## Użycie w istniejącej aplikacji

1. W zakładce **Dane** wybrać **Włącz zapis z wersją planu**. Potwierdzenie pobiera pełną kopię sprzed operacji i korzysta z jawnej migracji C. Startup nie wykonuje migracji. Trwający wcześniej trening pozostaje dawnym zapisem; nowe snapshoty dotyczą dopiero przyszłych sesji.
2. W zakładce **Trening** wybrać jednostkę i rozpocząć. Zapamiętane zostają aktualnie wyświetlane parametry źródłowego planu, z jawnym statusem niezweryfikowanych. Nie jest aktywowany projekt 34 pozycji V2 ani wybór nowych maszyn D2.
3. W istniejącym szybkim formularzu wpisać kg/reps, ołówkiem poprawić poszczególne serie albo dodać/usunąć serię. Każda nowa wykonana seria ma własne trwałe ID; korekta je zachowuje, nowa sesja nie kopiuje ID poprzednich wykonań. Nie podpowiadamy przykładowego initialKg jako wyniku nowej sesji.
4. Zakończyć trening. W kalendarzu otworzyć sesję, przejrzeć jej parametry ze snapshotu i poprawić serie. Zmiana bieżących parametrów nie przepisuje snapshotu. Ostatni wynik i statystyki dotyczą tego samego zapisanego kontekstu; historia oznacza dawny zapis i inne konteksty osobno. Stare rekordy i statystyki pozostają dostępne przez stare sesje.
5. Ten sam przycisk **Eksportuj JSON** po włączeniu zwraca pełne v3. Ten sam import potrafi odtworzyć taką kopię w pustym profilu i zastąpić bieżący stan po potwierdzeniu, z zachowaniem kopii sprzed importu. Tryb bez nowego dziennika nadal eksportuje v2; odczyt v1/v2 działa nadal.

## Dane i bezpieczeństwo

`model/journal.mjs` używa kontraktów A, a `legacy-model.mjs` projektuje nowy zapis do pełnego backupu B. Używany jest istniejący transakcyjny magazyn C, bez nowej bazy/schematu. `trainingJournal` w źródłowym dokumencie przechowuje obserwowany model i snapshoty; nowe sesje/wpisy mają referencje, a serie ID i opcjonalne powiązanie z celem. Stara reprezentacja wyników pozostaje pełną projekcją kg/reps, nie znika. Metadane i snapshoty są walidowane przed wspólnym commitem, a sukces następuje po oncomplete. Nie ma drugiego niezależnego zapisu do innej bazy.

Wersje obserwowanego planu są identyfikowane hashem rzeczywistych parametrów bez notatek; powstają przy rozpoczęciu nowej sesji, nigdy dla dawnych treningów. Kolejność/parametry istniejącej aplikacji są zachowane w `legacyExercise`. Typed reps/RIR/tempo/rola/strona/konwencja są nieokreślone, zamiast udawać zatwierdzone cele V2. Wariant ma status źródłowy nieustalony; zmiana parametrów tworzy odrębny kontekst porównań. To konserwatywna granica, nie rozpoznawanie sprzętu po nazwie. PUSH-A-4 pozostaje dipami legacy; nowej maszyny nie dodano i nie przejęła ich wyników.

Notatki wspólne pozostają legacy-shared; nie przypisano im autora trenera. Snapshot nie zamienia notatek użytkownika w instrukcje. Nie zmieniono dawnego tonażu ani nie mnożono wyników przez dwa. Import/eksport zachowuje wszystkie obsługiwane rekordy i pola dodatkowe. Import v3 w UI przyjmuje pełne, odtwarzalne kopie źródłowe dziennika A–C/tej części; ogólna lub przyszła v3, której nie można odtworzyć w całości przez ten adapter, jest jawnie odrzucana bez zapisu. Biblioteka B nadal odczytuje ją niezależnie — nie redukujemy jej po cichu do kg/reps.

CSS, kolory, karty, nawigacja, ikony, tożsamość PWA i nazwa bazy bez zmian. Dodano przycisk w Dane i krótkie etykiety kontekstu wewnątrz obecnych kart. Moduł znajduje się w tym samym zweryfikowanym shellu offline. Nie uruchomiono niczego na historii użytkownika i nie opublikowano aplikacji.

## Co pozostaje

**Nie działa jeszcze jako pełny nowy V2:** osobne zatwierdzone cele serii/back-off, elastyczne segmenty dropsetów, L/P i świadome kopiowanie stron, dwa odrębne wyniki narciarza/szrugsów w dwóch rundach oraz podgląd/import/aktywacja całego poprawionego planu. Wersja wykonań 1 obsługuje płaskie serie i odrzuca struktury specjalne zamiast deklarować ich obsługę. Można ręcznie zapisać różne ciężary/dodatkowe zwykłe serie, ale nie nazywamy tego gotowym edytorem back-off/drop/grupy.

Następna część powinna rozszerzyć ten sam zapis i kontrolki o cele/struktury serii z zatwierdzonego projektu, rozdzielone instrukcje i warianty. O1–O3 (maszyna, niepotwierdzone parametry pięciu wariantów, konwencje) pozostają jawnie nieokreślone; model A ma na nie pola, nie dodano arbitralnych wartości ani nowego planu. Aktywacja wymaga oddzielnej decyzji właściciela. Przed pierwszym normalnym treningiem według całego V2 potrzebne są te funkcje, zatwierdzenie parametrów, następnie zatwierdzony HTTPS i próba fizycznego telefonu. Hosting, OAuth i Drive nie są częścią tego PR.

## Testy

Istniejące node:test/unittest/Playwright, bez nowej infrastruktury. `tests/test_journal.py` ma cztery scenariusze użytkowe: trening z różnymi seriami, zamknięcie/restart, korekta/tonaż i v3 na pustym profilu; odmowa nieodtwarzalnej v3 bez utraty dodatkowych pól; błąd zapisu/retry; anulowanie, niezmienność snapshotu po zmianie parametrów i przerwane włączenie/retry. Widok mobilny sprawdzony w Chromium (390 px), dotychczasowa bramka Matrix porównuje 12 ekranów w trzech szerokościach. Z dawnych kontroli niezmienności wyłączono celowo modyfikowany app.js; CSS/ikony/manifest i porównania wizualne pozostały. Wynik pełnej regresji i CI jest w PR. Fizycznego Androida i rzeczywistych danych użytkownika nie testowano.

Lokalnie: **68/68 Node, 54/54 Python/Chromium — PASS**, bez pominięć; po doprecyzowaniu scenariuszy ponowiono **4/4 testy dziennika — PASS**, w tym rzeczywisty błąd zapisu wyniku/zachowany draft, retry i nowe ID przy kopiowaniu poprzednich serii do kolejnej sesji. Składnia JS, `git diff --check`, kontrola workera i build `dist/functional-journal-part-1` przeszły; wydanie `0913feea029b7ebdedc00c1e`, bez publikacji. Kontrole GitHub Actions dla aktualnego SHA oraz ich linki są w PR.
