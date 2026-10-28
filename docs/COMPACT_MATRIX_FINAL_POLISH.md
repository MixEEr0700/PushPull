# Compact Matrix v0.4 — końcowy szlif po PR #96

Baza: `main`, `3d581cfccafc476a0e07135dd2f378f8c9f12b50` (scalony PR #96). Zakres: załączone polecenie oraz końcowe ustalenia właściciela w PR #97 z 28.10.2026, 09:30:43 UTC. Bez Issue #94 i bez przebudowy aplikacji.

## Zmiany UI

- Numer 22 px na wypełnionym kwadracie `#176B45`, biały tekst; nazwa 20,5 px (około 14% więcej niż 18 px w PR #96), pogrubiona, bez obcinania. Parametry pochodzą z dotychczasowych widoków planu, kolor `#A9B7AF`.
- Rzeczywiste wyniki `#39FF74`, 13 px / 600; wiek ostatniej zmiany pozostaje szary, mniejszy. Bez zmian kompresji równych serii, porządku 10/10/9, L/P, drop, back-off, rund i kontekstów.
- Ikona notatnika jest osobnym przyciskiem obok chevrona, wyłącznie na rozwiniętej karcie. Brak zagnieżdżania przycisków. Otwiera/zamyka obszar Notatki bez zamykania ćwiczenia. Po uruchomieniu obszar jest schowany, także przy zachowanym szkicu. Jego zamknięcie nie kasuje tekstu. Stan widoku jest wyłącznie w pamięci i rozdziela właściciela, plan/wariant i ćwiczenie.
- Obszar Notatki zawiera wyłącznie własny tekst `userNotes`. Nie renderuje instrukcji trenera, tekstów źródłowych, historycznych ani osobnego readonly. Pusta notatka: dyskretny plus, istniejąca: tekst z ołówkiem i pełna edycja. Dane źródłowe/proweniencja pozostają w bazie.
- Kolejność aktywnego formularza: nagłówek → opcjonalne Notatki → dwa szybkie pola → opcjonalne serie → cztery dolne przyciski. Pierwszy rząd: Zapisz wynik / Edytuj serie lub Zapisz korektę / Zwiń serie. Drugi: Historia / Statystyki. Nie ma przycisków pomiędzy polami i seriami, drugiego formularza pod nimi ani powielonych kontrolek Historii/Statystyk. Po zatwierdzonym zapisie lub przejściu do historii/statystyk pozostają cztery akcje w dwóch rzędach, pod panelem. Edytuj serie otwiera dotychczasowy formularz i rozwija jego wiersze; nie zapisuje wyniku.
- Usunięto instrukcje opisowe o szybkim wpisie i powielaniu segmentów. Zachowano obowiązkowy wybór znaczenia kg dla planów, gdzie jest nieustalone, oraz ostrzeżenia/confirmy/komunikaty walidacji.
- Auto-wysokość notatki uwzględnia obramowanie `border-box`. Nowy test odtworzył niedoszacowanie o 2 px; poprawka usuwa różnicę między `scrollHeight` i `clientHeight`, bez wewnętrznego przewijania.

## Uzupełnienie po decyzji właściciela w PR #97

Decyzja 09:30:43 UTC zastępuje wcześniejszy pomysł wspólnej edycji źródeł. Nie wdrażamy nakładki ani nowego kontraktu. Zmieniono tylko projekcję/edycję własnej notatki i udostępniono ten sam edytor podczas przygotowania zapisanego planu.

### Własne notatki i kontekst

- `coachInstructions`, teksty `owner`, historyczne `exercises[].notes`, źródła, rewizje i snapshoty zachowują oryginalną zawartość. W treningu i kalendarzu nie są doklejane do Notatek. Dokumentacja źródłowa nadal pozostaje w podglądzie definicji planu i kopiach.
- Własny zapis nadal korzysta z `userNotes` i istniejącego ID `user:<planVersionId>:<exerciseId>`, `origin:user`, `sessionId:null`. Odczyt sprawdza też właściwe ćwiczenie i obecność wariantu w tej wersji. Usunięto fallback po samym ID ćwiczenia: arbitralnie nazwany stary rekord nie dowodzi przypisania do bieżącej wersji. Rekordy te zostają zachowane, bez kopiowania, scalania ani migracji.
- Jeżeli jedna wersja planu zawiera różne warianty tego samego ćwiczenia, obecny kontrakt nie rozróżnia ich w ID notatki. Edytor blokuje taki niejednoznaczny kontekst zamiast pożyczać tekst lub wprowadzać nową konwencję identyfikatorów. To jawne ograniczenie, nie migracja.
- Legacy ze snapshotem obserwowanej wersji może zapisać własną notatkę dla tego kontekstu do istniejących `userNotes`; nie edytuje `legacyExercise` ani tekstu rejestru. Legacy bez wersji/snapshotu nie ma udowodnionego przypisania: widok informuje o braku kontekstu, nie pokazuje źródłowych tekstów i nie tworzy go automatycznie. Należy jawnie zapisać/aktywować plan albo użyć istniejącej opcji wersjonowania dla przyszłych sesji. Dawne teksty nadal są w danych/kopiach.
- Zapis sprawdza ID, powiązania, bazowy tekst i rewizję. Kolizja z notatką sesyjną lub źródłową blokuje zapis. Potwierdzenie pojawia się po dotychczasowym zatwierdzonym commicie; CAS i walidacja bazy pozostają bez zmian.
- Szkice nadal używają dotychczasowych tokenów, bazy, localStorage i pamięci edytora. Różne źródła nie mają automatycznie wybieranego zwycięzcy. Zachowano anulowanie, ochronę kolizji, pobieranie i zachowanie tekstu po błędzie. Dla kontekstu bez jednoznacznego powiązania istniejący szkic można pobrać bez przypisywania go do innej wersji. Nie rozszerzono kodeka/collectora v6; szkic UI nadal nie jest zatwierdzoną notatką w kopii wyników.

### Pierwsza notatka przy przygotowaniu planu

Istniejący plik `pushpull-plan` v1 **nie zawiera `userNotes`**. Nie dodano do niego nowego pola ani nie interpretowano instrukcji jako notatki. Najmniejsza ścieżka: **Dane → Plany → import → Zapisz plan bez aktywacji → podgląd zapisanej wersji → rozwiń jednostkę → plus przy ćwiczeniu → zapisz Notatki**. Można ją wpisać przed pierwszym treningiem i przed aktywacją; trening korzysta potem z tego samego rekordu i ID. Sam podgląd nadal niczego nie zapisuje. Zapis notatki wymaga osobnego zatwierdzenia, nie aktywuje planu i nie zmienia rozpoczętej sesji.

Wbudowany, jeszcze niezapisany V2 pozostaje podglądem bez inicjalizacji notatki. Dla niego zapis jest dostępny po jawnej aktywacji. Zapisany plan importowany umożliwia przygotowanie przed aktywacją. Eksport **pliku planu** pozostaje definicją i nie zawiera własnych notatek; zatwierdzone `userNotes` obejmuje istniejąca pełna kopia danych. Żadnych zmian formatów.

## Zachowane mechanizmy

Bez zmian w schemacie IndexedDB v2, modułach protokołu przyrostowego, CAS, readback, `strict complete`, modelach/źródłach planów, rotacji, wynikach, tonażu, historii, statystykach, Drive oraz kodekach backupów v1–v6 i przywracaniu. Bez automatycznego kasowania danych. Góra aplikacji, wybór treningu, kalendarz, Dane i nawigacja z ikonami pozostają w dotychczasowym wyglądzie. Wejście do Dane nadal nie uruchamia `ensureFull()`.

## Testy i pomiary

Poprzedni HEAD `80e592d` miał pełne CI PASS: run `40659025224` (219 Node + 211 Chromium/PWA). To wynik sprzed uzupełnienia, nie wynik obecnego kodu.

Bieżące uzupełnienie: pełny Node **221/221 PASS**, kontrola składni, zgodność worker/hash i build produkcyjny PASS (końcowy release `e9dec92ab801b7bc064fa7df`, bez wdrożenia). Pełną regresję Chromium/PWA wykonuje wymagany workflow PR; końcowy status i link są w PR. Cztery nowe przypadki Chromium **4/4 PASS**; osobny przebieg zachowania rejestru legacy **1/1 PASS**. Nowe przypadki obejmują przygotowanie notatki bez aktywacji, offline/restart, ten sam ID ćwiczenia w kolejnej wersji planu, wyczyszczenie tekstu jako własną rewizję, stare nieprzypisane rekordy i legacy ze snapshotem. Zachowano dokładne porównania źródeł, snapshotów i historii, testy quota i kolizji oraz mobilne 360/390/412 px. W lokalnym przebiegu wystąpiły niestabilne timeouty oczekiwania UI (5 s), m.in. przy otwieraniu bazy/aktywacji i potwierdzeniu zapisu; brak stwierdzonego naruszenia asercji danych. Końcową asercję dawnego testu legacy dostosowano do zatwierdzonej zmiany: porównuje cały niezmieniony rejestr ćwiczeń zamiast oczekiwać zapisu nowej notatki do tekstu źródłowego. Nowe testy osobno weryfikują pełny zapis i odczyt `userNotes`. Oddzielny przypadek 10/10/9 przeszedł na poprzednim runtime `80e592d` i obecnym kodzie. Nie rozstrzygamy na tej podstawie przyczyny pozostałych timeoutów ani nie zwiększamy limitów testów. Wyniki końcowej lokalnej próby i pełnego CI są podane w PR. Nie wykonano odbioru fizycznego Pixela 9 ani prawdziwego konta Google.

## Regresja wykryta przez pełne CI i poprawka

Przebieg `40668269328` wykrył dwa niepowodzenia. W trybie observed rzeczywistą przyczyną niedostępności przycisku wznowienia szkicu po aktualizacji było dodanie `positionId` do projekcji starego ćwiczenia. `bindingFor()` korzysta z tego pola; dawne szkice wiążą tę wartość jako `null`, więc zmieniony widok przestał odpowiadać ich kontekstowi. Usunięto zbędne `positionId` z tej projekcji, zamiast zmieniać reguły zgodności lub przepisywać szkice. Wersja potrzebna Notatkom nadal pochodzi ze snapshotu. Nie zmieniono przechowywanych danych, bindingu ani protokołu szkiców.

Drugi test wizualny nadal otwierał dawny edytor tekstu źródłowego bez wersji planu. Teraz jawnie aktywuje zapisany V2 przed sprawdzeniem edytora własnych notatek; wszystkie asercje mobilne i niezmienności danych pozostały. Ochronę niewersjonowanego legacy sprawdzają osobne testy.

Po poprawce lokalnie **3/3 PASS**: wizualny kontrakt 360/390/412 px, rzeczywista aktualizacja PWA z historycznego release ze szkicami source/observed/V2 oraz Notatki observed po restarcie. Zachowano dokładne porównania bazy, zapisanych wyników, wszystkich szkiców oraz ich skuteczne wznowienie i zatwierdzenie. Node po zmianie projekcji: **18/18 PASS** (`v2-plan`, `compact-notes`, `draft-collector`). Pełny workflow końcowego HEAD i jego wynik są podane w PR.

## Pomiary przed/po

**Poniższe pomiary dotyczą runtime `d74d298` / testowego HEAD `80e592d`, przed obecnym uproszczeniem Notatek. Nie są pomiarem nowego kodu.** Nie powtarzano zakończonych benchmarków ani nie optymalizowano protokołu w tym uzupełnieniu.

Chromium/Linux, CPU ×4, izolowane profile i dokładnie zachowane syntetyczne fixture’y A–E. Baza to bieżący `main` / PR #96. Historyczne wyniki 125/221 ms i 195/319 ms nie są uczciwą dzisiejszą kontrolą: również niezmieniony `main` działał dziś znacznie wolniej. Dlatego po pierwszym pomiarze zmian wykonano nowy kontrolny przebieg bazy. Serie uruchamiano kolejno, bez innych lokalnych testów. Kolejność nie była losowana; próbka jest mała. Nie zmieniono limitów, throttlingu ani walidacji i nie odrzucono najgorszych prób. [Pełne agregaty, zegary, hashe i orakle](performance/compact-matrix-final-polish.json).

| Baza | klik → strict complete przed mediana / p95 | po mediana / p95 | próbkowany heap JS max przed / po |
| --- | --- | --- | --- |
| 4 sesje | 690,2 / 1056,6 ms | 631,6 / 1154,4 ms | 12,8 / 12,3 MiB |
| 40 sesji + raw 4 MiB i checkpointy | 1043,7 / 1654,9 ms | 1074,7 / 3949,6 ms | 22,2 / 19,6 MiB |

Każdy wariant ma 8 zapisów (4 nowe + 4 korekty); empiryczne p95 jest maksimum. Zegar to pierwszy natywny callback transakcji `strict complete` (także zachowany `event.timeStamp`), nie toast ani odczyt przez Playwright. Orakle historii, snapshotów i archiwów PASS, identyczne hashe fixture’ów. Heap jest próbkowanym JS, nie całkowitym RAM ani gwarantowanym szczytem.

**Nie potwierdzono celu p95 poniżej 1 s w dzisiejszej syntetyce.** Przekroczenia ma również bazowy `main`. Po zmianach najgorszy zapis dużego wariantu trwał 3949,6 ms i jest jawnie zachowany. W pierwszej próbce przygotowanie indeksu miało 1874,3 ms, readback 1093,7 ms (inkluzywne przedziały, zawierają oczekiwanie; nie są wyłącznym czasem CPU). Moduły realizujące te operacje mają identyczne SHA-256 przed/po. Nie wykazano związku z nowym UI, ale sam brak zmiany kodu nie dowodzi braku regresji ogona. Potrzebny jest odbiór na Pixelu 9; nie wprowadzano poza zakresem optymalizacji protokołu, aby ukryć ten wynik.

Pierwszy pomiar nawigacji obejmował też powrót do klienta Playwright (RPC):

| Dane, offline, n=5 | przed mediana / p95 | po mediana / p95 | żądania IDB |
| --- | --- | --- | --- |
| 4 sesje | 66,1 / 149,7 ms | 153,8 / 360,4 ms | 0 |
| 40 sesji + raw 4 MiB | 75,3 / 217,4 ms | 540,2 / 677,9 ms | 0 |
| 400 sesji + raw 4 MiB | 95,4 / 395,2 ms | 109,1 / 970,4 ms | 0 |

Dodatkowo rozdzielono zegar wewnątrz strony: gotowy DOM wykryty przez MutationObserver oraz dwie klatki rAF jako możliwość wyświetlenia. Zachowano oryginalny czas RPC, zamiast zastępować go korzystniejszą miarą. To odrębny pomiar diagnostyczny n=5, bez zmiany aplikacji.

| Dane, offline | DOM przed mediana / p95 | DOM po mediana / p95 | dwie klatki przed mediana / p95 | dwie klatki po mediana / p95 |
| --- | --- | --- | --- | --- |
| 4 sesje | 17,6 / 59,5 ms | 22,1 / 62,1 ms | 86,8 / 156,7 ms | 62,8 / 169,1 ms |
| 40 sesji + raw 4 MiB | 15,6 / 69,7 ms | 43,5 / 190,8 ms | 65,2 / 173,6 ms | 141,0 / 892,7 ms |

Wszystkie próby nawigacji: 0 żądań IndexedDB i brak `ensureFull()`. Zegary DOM/rAF nie są pomiarem ekranu fizycznego telefonu. Bieżące porównanie nie uprawnia do deklaracji zachowania p95 zapisu na Androidzie bez rzeczywistego odbioru.

## Korekta synchronizacji testu PWA po pierwszym CI

Pierwszy workflow `40654345171` zakończył się timeoutem jednego przypadku (`test_local_backup_v4`, oczekiwanie na `serviceWorker.controller`). Lokalny przebieg tego oryginalnego przypadku przeszedł, więc nie potwierdzono deterministycznej przyczyny timeoutu ani błędu aplikacji. Nie zmieniano service workera ani logiki aktywacji.

Oczekiwanie rodziny testów lokalnych kopii/izolowanego podglądu zostało oparte na bezpośrednim odczycie kontrolera i czasie monotonicznym Pythona, niezależnie od dostarczania klatek animacji. Zachowano warunek `controller !== null`, dotychczasowy limit 30 s i wszystkie asercje danych. Rejestracja `ready` nadal nie wystarcza. Dwa nowe testy z rzeczywistym, testowym service workerem sprawdzają odrzucenie aktywnej rejestracji bez kontrolera oraz wymagane przejęcie strony, także przy wstrzymanym czasie wirtualnym. Probe nie dotyka cache aplikacji ani IndexedDB. To korekta synchronizacji w harnessie, nie deklaracja odtworzenia pierwotnego błędu CI.

Na HEAD `80e592d` zmiany po pomiarach dotyczyły wyłącznie testów i raportu; workflow `40659025224` przeszedł. Obecne uproszczenie Notatek zmienia runtime, więc jego SHA-256 jest inny; historycznych czasów nie traktujemy jako pomiaru obecnego HEAD.
