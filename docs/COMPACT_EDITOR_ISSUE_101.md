# Issue #101 — odtwarzanie L/P i dodawanie dropsetów

Baza: aktualny `main` po PR #100, `0a7b1ac62f75c9d3fffd3c750807ec369b065d00`. Gałąź `compact-editor-issue-101`, osobny PR; bez scalania i ręcznego wdrożenia.

## Przyczyny i odtworzenie na bazie

Dwa problemy odtworzono na syntetycznych danych przed zmianami:

- Dla opcjonalnego wykonania L/P (`PUSH-A-6`) jawne wykonanie obu stron tworzyło sześć rekordów. Po usunięciu trzech par `add-set` wybierał strony na podstawie **pozostałych wierszy**. Przy pustej tablicy otrzymywał `[null]`, czyli pojedynczy rekord. Wymagane L/P w planie miało osobną ścieżkę; nie każdy rodzaj ćwiczenia był dotknięty tym błędem.
- Po usunięciu wszystkich wierszy dropsetu dodawano serię `setId: null`, z jednym segmentem. Przycisk segmentu był dostępny tylko dla istniejącego celu oznaczonego jako drop w planie, więc znikał. Walidator dodatkowo odrzucał wiele segmentów bez takiej definicji. Samo pokazanie przycisku nie rozwiązywałoby trwałego zapisu.

## L/P i pusty szkic

Decyzja wykonania `executionMode` jest częścią **lokalnego stanu szkicu**, nie nowym polem planu lub schematu IndexedDB. Ustalamy ją przed usunięciem wierszy, z wymagania planu albo jawnego, kompletnego wykonania w edytorze. Nowe serie korzystają z tej decyzji, nie z liczby pozostawionych wierszy. Szkic zachowuje ją w buforze i IndexedDB po restarcie.

- Wspólny wiersz nadal steruje dwiema rzeczywistymi stronami. Każdy rekord i segment ma niezależne ID. Nowe pola są puste.
- Zapis pojedynczy pozostaje pojedynczy. Nie powielamy historycznego wyniku według nazwy ćwiczenia ani dzisiejszych założeń.
- Stary pusty szkic opcjonalnego ćwiczenia, który nie zawiera decyzji wykonania, jest **nieustalony**. Dodanie jest zablokowane do jawnego wyboru; z usuniętych już danych nie odtwarzamy domysłu.
- L/P wymaga zgodności konwencji kg z planem/sesją. Nieznane kg i kg łącznie nie upoważniają do dodawania nowych par. Istniejące historyczne wartości i asymetrie pozostają zachowane w osobnych szczegółach; szybkie pola ich nie nadpisują.
- Pusty szkic jest odtwarzalny, ale nie jest poprawnym wynikiem. Zwykły widok nie zawiera przycisków rozdzielania/scalania.

Nowa seria najpierw korzysta z brakującej przepisanej serii, zachowując jej rolę/ID celu. Po wykorzystaniu wszystkich celów zwykłe dodatkowe wykonanie ma `setId: null`. Grupy zachowują wyłącznie dozwolone rundy i członków.

## Dwa przyciski i segmenty

Pod wierszami są dwa równe przyciski: **+ Dodaj serię** i **+ Dodaj dropset**. Przy kilku możliwych rodzicach drugi otwiera jawny wybór serii według stabilnego ID. Nie wybiera po cichu pierwszej/ostatniej. Przy jednym jednoznacznym rodzicu dodaje bez zbędnego wyboru.

Nowy segment znajduje się pod właściwą serią jako `+1`, `+2` itd., z własnym koszem i pustymi kg/powtórzeniami. Usunięcie wszystkich dodatkowych segmentów nie usuwa możliwości ponownego dodania. Jeśli usunięto również wszystkie serie rodzicielskie, trzeba najpierw dodać serię — nie tworzymy fikcyjnego rodzica ani wykonanych wartości. Zmiana celu podczas wyboru powoduje odmowę działania zamiast użycia innego indeksu.

Dla wspólnych L/P dodawany/usuwany segment dotyczy obu rzeczywistych stron dokładnie raz. Dla zastanej asymetrii wybór wyraźnie wskazuje L albo P; nie normalizuje istniejących wartości ani struktury drugiej strony.

[Wspólne L/P — rzeczywisty Chromium, 360 px](screenshots/issue101/paired-360.png) · [Dwa segmenty drop i przyciski, 360 px](screenshots/issue101/drop-360.png). Są to syntetyczne zrzuty desktopowej przeglądarki, nie zdjęcia Androida.

## Jawne rozszerzenie danych wyniku

Issue #101 wprost dopuszcza bezpieczne rozszerzenie, jeśli dotychczasowy kontrakt nie obsługuje ad hoc dropsetu. Wprowadzono opcjonalne **`performance.rows[].dropOrigin: "user"`** dla dodatkowych segmentów na serii bez przepisanego dropu.

- Uznajemy go za faktyczny drop wyłącznie przy co najmniej dwóch segmentach. Nadal obowiązują identyfikatory, liczby, projekcja, referencje do planu, stron i rund.
- Wiele segmentów poza przepisanym dropem **bez** tego jawnego oznaczenia pozostaje błędem. Nie osłabiono kontroli projekcji ani integralności.
- Oryginalne `setId`, role back-off/main, grupa, runda i snapshot pozostają bez zmian. Nie dopisujemy definicji dropu do planu ani nie przedstawiamy zwykłego dodatkowego segmentu jako przepisanej instrukcji trenera.
- Istniejące nieznane metadane o tej nazwie pozostają czytelne tak jak wcześniej. Nie są upoważnieniem do dropu ad hoc. Gdy nowa operacja wymagałaby ich nadpisania, odmawia bez zmiany danych.
- Karty i historia rozpoznają rzeczywisty drop także poza pierwotnym planem. Tonaż i statystyki nadal sumują zapisane segmenty; segmenty nie stają się dodatkowymi seriami. Trzy pary `10 × 24 kg` dają 1440 kg; dodatkowy segment na parze daje 1920 kg, jeśli również wykonano `10 × 24 kg` na obu stronach. Nie dodano mnożnika ×2.
- Sygnatury pomiarów starych danych pozostają identyczne, aby nie wymuszać przebudowy indeksów przy aktualizacji. Nowe dane zawierają rzeczywistą strukturę dropu w porównaniach.

To rozszerzenie **danych wyniku**; wersja protokołu/schemat IndexedDB v2, magazyny, CAS, readback i `strict complete` pozostają niezmienione. Nie wykonujemy migracji, konwersji ani kasowania danych.

## Kopie i zgodność wersji

Nie zmieniono kodeków ani obwiedni plików v1–v6, Drive ani przywracania. Pełny źródłowy model wyniku zawiera marker i segmenty; istniejące hashe/digesty obejmują te pola. Roundtrip sprawdza aktualne odtworzenie v3 oraz odczyt v4/v5/v6 i dokładną materializację protokołu z zachowaniem archiwów/nieznanych pól.

**Starsze kopie nadal są czytane. Starsza aplikacja nie obsługuje nowych dropsetów ad hoc.** Po zapisaniu takiego wyniku powrót do PR #100 lub starszego klienta może zakończyć się bezpieczną odmową walidacji danych/kopii. Nie deklarujemy zgodności nowych danych ze starym walidatorem. Należy użyć zaktualizowanej aplikacji; nie resetować bazy, żeby ominąć błąd. Nie zmieniamy historii w celu umożliwienia downgrade.

Stare niewersjonowane/proste zapisy nie mają struktury rodzic/segment ani zweryfikowanych definicji. Ich przycisk dropsetu jest nieaktywny i ma widoczne wyjaśnienie. Zachowano ich edycję oraz dodawanie/usuwanie zwykłych serii; nie wykonujemy automatycznej konwersji takiej historii. Nowe dropsety ad hoc obejmują wersjonowane treningi V2, również dodatkowe serie i rundy istniejących grup.

## Weryfikacja

Dane i profile były izolowane i syntetyczne. Nie otwierano profilu telefonu ani produkcyjnego Drive.

- Nowe Node: delete-all → JSON/restart → add L/P, stare puste/pojedyncze szkice, nieznane/łączne kg, wskazanie rodzica, puste segmenty, odtworzenie segmentów po usunięciu, nowe serie bez celu, asymetria/brak pary, back-off i grupy, stare sygnatury indeksu, nieznane metadane oraz protokół/v3–v6 z Unicode i dużym archiwum.
- Chromium: 1/2/3 pary, usunięcie do zera i wznowienie, jeden wspólny wiersz, ID i tonaż bez drugiego mnożnika; drop na wybranej i nowej serii, usuwanie wszystkich dzieci i rodziców, powrót po restarcie; błędne/puste dane, abort zapisu i zachowane szkice; asymetria wybranej strony, historia i pełne v3 odtworzone w drugim izolowanym profilu.
- 360/390/412 px: dokładnie dwa równe przyciski obok siebie, wysokość minimum 44 px, bez poziomego przepełnienia. Widok utrzymuje kompaktowe numery/segmenty i nie powtarza celów, tempa/RIR.
- Offline i rzeczywisty update z PR #100: oba stare szkice pozostają dokładnie zachowane. Pusty opcjonalny wymaga wyboru, usunięte segmenty można odtworzyć. Zapis/zakończenie, rotacja, wynik, ID i dane są sprawdzane po restarcie offline.

Lokalne wyniki: pierwszy pełny Node **245/245 PASS**, następnie końcowy pełny zestaw po dodatkowej ochronie metadanych **246/246 PASS**. Chromium **30/30 PASS**, następnie **8/8 PASS** obejmujące wzmocnioną kontrolę zachowania indywidualnych segmentów, update PR #100 i Compact Matrix. Końcowe przypadki nowej funkcji i aktualizacji po ochronie metadanych: **7/7 PASS**. Build produkcyjny i worker/hash PASS, bez wdrożenia. Pełny wymagany workflow PR obejmuje również dotychczasowe CAS/quota/readback, backupy, historię, plany, notatki, PWA i aktualizacje; konkretny commit i wynik znajdują się w PR.

Wczesne niepowodzenia dotyczyły przygotowania nowych testów: niedozwolonej wartości `consistency` w syntetycznych dowodach v6 oraz oczekiwania na aktywną sesję po prawidłowym zakończeniu treningu. Poprawiono scenariusze, bez zmiany walidatorów v6 i bez osłabiania asercji danych/rotacji.

## Ograniczenia i odbiór

Brak fizycznego testu Pixel 9, natywnej klawiatury Androida oraz prawdziwego konta Drive. Nie powtarzano zakończonych benchmarków PR #100 i nie przypisujemy ich czasów tej poprawce. Ten PR nie potwierdza nowego p95 ani odbioru na telefonie. Mechanizm trwałego zapisu nie został przebudowany.

Po przeglądzie i wdrożeniu przez właściciela: sprawdzić release, opcjonalne i wymagane L/P, usunąć do zera, zamknąć aplikację, wznowić i dodać serię; sprawdzić dwa rekordy w zapisanym wyniku i tonaż. Dla dropu usunąć wszystkie dzieci, wznowić, wskazać serię i dodać segment; sprawdzić też dodatkową serię oraz zachowanie starej asymetrii. Zakończyć trening ze szkicem offline, ponownie otworzyć historię. Zachować kopię; nie resetować bazy. Dalsze zmiany schematu, migracji starych zapisów lub synchronizacji nie należą do tego PR.
