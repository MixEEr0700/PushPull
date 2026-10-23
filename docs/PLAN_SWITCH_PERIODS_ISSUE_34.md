# Zmiana zapisanego planu i okresy używania — Issue #34

Baza: `main` po PR #35, commit `c40e173`. Zatwierdzony kierunek: [plany i statystyki](PLANY_I_STATYSTYKI_KIERUNEK_2026-10-23.md). Issue #36 pozostaje poza zakresem.

## Obsługa

**Dane → Plany treningowe → Aktualny plan → Zmień plan** otwiera krótki wybór wcześniej zapisanych wersji możliwych do aktywacji. Nie trzeba ponownie importować pliku. Aktualna wersja, niezidentyfikowana historia i niezapisany podgląd V2 nie są kandydatami. Brak kandydatów jest jawnie opisany; dotychczasowy import i podgląd pozostają dostępne.

Wybór/podgląd nie zapisuje danych. **Aktywuj wybrany plan dla następnych treningów** wymaga jednego potwierdzenia z nazwą wersji, pierwszą jednostką oraz informacją o ochronie rozpoczętej sesji. Dotychczasowy mechanizm pobiera i zachowuje pełną kopię przed zmianą. Anulowanie niczego nie aktywuje. Identyczny już aktywny plan nie tworzy zdarzenia i nie resetuje rotacji.

Po zmianie przyszły cykl zaczyna się od pierwszej jednostki według `order` wybranej wersji. Nie powstaje automatycznie sesja. Powrót do V2 używa zapisanej wersji i jej definicji; nie odbudowuje ich z dzisiejszego pliku w kodzie ani nie zmienia starych ID/instrukcji. Importowane wersje nadal wykorzystują `stageActivation` z PR #24.

## Daty: odczyt, bez migracji

Okresy są wyliczane z `trainingJournal.activations` w zapisanej kolejności zdarzeń. Początek to rzeczywisty timestamp aktywacji, koniec to timestamp następnego przełączenia. Ostatni okres jest otwarty tylko przy zgodności z aktywną wersją. Powrót V2 → V3 → V2 daje dwa oddzielne okresy V2. Data końca nie jest sztucznie pomniejszana o dzień; dzień przełączenia może występować na obu granicach. Dokładne timestampy pozostają zachowane, a daty interfejsu są w `Europe/Warsaw`.

Nie korzystamy z dat importu, źródła planu ani zegara odczytu do odtwarzania brakujących aktywacji. Brakujące, nieprawidłowe lub cofające się timestampy dają okres nieustalony. Nie sortujemy zdarzeń według zegara, nie usuwamy starych wpisów i nie dopisujemy dat wstecz.

Gdy brak pełnego okresu, pierwszą/ostatnią datę zakończonych treningów pokazujemy wyłącznie dla jednoznacznego snapshotu lub katalogu `session-start`/`recorded`, z etykietą **„Okres aktywacji nieustalony; treningi od … do …”**. To daty sesji, nie granice obowiązywania planu. Sama lista ID szkieletu, dawny katalog `legacy-current-only` i historia nieprzypisana nie stanowią dowodu okresu. Bez dowodu widnieje **„Brak wiarygodnych dat”**. Korekta historycznej daty sesji zmienia wyłącznie zakres treningów, nie aktywacje.

## Ochrona rotacji, historii i kopii

Nowe zdarzenie aktywacji zawiera opcjonalne `ongoingSessionId`, tylko gdy w chwili zmiany istnieje otwarta sesja. Jest to referencja do istniejącego ID, walidowana przy zapisie/odtwarzaniu. Nie zmienia sesji, wyniku ani snapshotu. Dzięki temu zakończenie starego treningu V2 po V2 → V3 → V2 nie przesuwa nowego cyklu V2, nawet jeśli zegar wskazał identyczne timestampy. Nowa sesja przesuwa rotację jak dotychczas.

Starsze logi bez tego pola są obsługiwane bez uzupełniania i migracji. Nowa referencja przechodzi przez istniejący bezstratny format kopii v3; stare kopie v1/v2/v3 pozostają czytelne. Nie zmieniono schematu IndexedDB, wyników, snapshotów, ID, notatek, szkiców, statystyk, kompaktowych skrótów z PR #35, ręcznego Drive, CSS, ikon ani nawigacji. Nowy picker używa obecnych klas i kontrolek Matrix.

## Odtwarzanie większych kopii

Wymagany scenariusz pełnego odtworzenia po powrocie do planu ujawnił `RangeError: Maximum call stack size exceeded` w dotychczasowym regexie tokenizującym JSON, na syntetycznej kopii około 24 MB. Zamieniono wyłącznie skanowanie stringów na iterację. `JSON.parse` nadal weryfikuje składnię, a kontrole duplikatów kluczy, reprezentacji liczb, schematu, relacji i sum kontrolnych pozostają. Format, zawartość i archiwa kopii nie są zmieniane ani usuwane. Ta poprawka jest niezbędna do testu odtwarzania w tym zadaniu; nie przebudowuje mechanizmu backupów.

## Weryfikacja i ograniczenia

Testy Node: oddzielne okresy, daty Warsaw/UTC, brakujące/błędne/cofające się daty, potwierdzona i nieprzypisana historia, korekta daty, powrót do zapisanych definicji, ochrona starej sesji, zwykła rotacja nowej oraz pełne odtworzenie z referencją aktywacji.

Testy Chromium: aktualizacja istniejącej PWA z zapisanym V2, wcześniej zaimportowanym V3, wynikiem i asymetrycznym szkicem; wybór/anulowanie i V2 → V3 → V2 bez ponownego importu; osobne okresy; odzyskanie i zapis szkicu offline; start od pierwszej jednostki; kompaktowy wynik, pełna kopia i odtworzenie na pustym profilu. Osobno: brak timestampu i edycja daty historycznej.

Wyniki pełnej regresji Node/Chromium oraz GitHub Actions: raport PR. Testy używają wyłącznie danych syntetycznych. Fizyczny Android i rzeczywisty Google Drive nie zostały przetestowane. Brakujących granic dawnych okresów nie da się wiarygodnie odtworzyć; nie są zgadywane. Pełne kopie nadal zawierają zachowane archiwa i mogą wymagać dłuższej walidacji — mechanizm archiwów nie jest przebudowywany w tym zadaniu.
