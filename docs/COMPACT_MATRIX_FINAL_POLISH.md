# Compact Matrix v0.4 — końcowy szlif po PR #96

Baza: `main`, `3d581cfccafc476a0e07135dd2f378f8c9f12b50` (scalony PR #96). Zakres: załączone polecenie właściciela z 28.10.2026. Bez Issue #94 i bez przebudowy aplikacji.

## Zmiany UI

- Numer 22 px na wypełnionym kwadracie `#176B45`, biały tekst; nazwa 20,5 px (około 14% więcej niż 18 px w PR #96), pogrubiona, bez obcinania. Parametry pochodzą z dotychczasowych widoków planu, kolor `#A9B7AF`.
- Rzeczywiste wyniki `#39FF74`, 13 px / 600; wiek ostatniej zmiany pozostaje szary, mniejszy. Bez zmian kompresji równych serii, porządku 10/10/9, L/P, drop, back-off, rund i kontekstów.
- Ikona notatnika jest osobnym przyciskiem obok chevrona, wyłącznie na rozwiniętej karcie. Brak zagnieżdżania przycisków. Otwiera/zamyka obszar Notatki bez zamykania ćwiczenia. Po uruchomieniu obszar jest schowany, także przy zachowanym szkicu. Jego zamknięcie nie kasuje tekstu. Stan widoku jest wyłącznie w pamięci i rozdziela właściciela, plan/wariant i ćwiczenie.
- Usunięto codzienne oznaczenia autorstwa z obszaru Notatki. Dane źródłowe/proweniencja pozostają w bazie. Ograniczenie edycji jest wyjaśniane dopiero przy otwartym edytorze dopisku.
- Kolejność aktywnego formularza: nagłówek → opcjonalne Notatki → dwa szybkie pola → opcjonalne serie → cztery dolne przyciski. Pierwszy rząd: Zapisz wynik / Edytuj serie lub Zapisz korektę / Zwiń serie. Drugi: Historia / Statystyki. Nie ma przycisków pomiędzy polami i seriami, drugiego formularza pod nimi ani powielonych kontrolek Historii/Statystyk. Po zatwierdzonym zapisie lub przejściu do historii/statystyk pozostają cztery akcje w dwóch rzędach, pod panelem. Edytuj serie otwiera dotychczasowy formularz i rozwija jego wiersze; nie zapisuje wyniku.
- Usunięto instrukcje opisowe o szybkim wpisie i powielaniu segmentów. Zachowano obowiązkowy wybór znaczenia kg dla planów, gdzie jest nieustalone, oraz ostrzeżenia/confirmy/komunikaty walidacji.
- Auto-wysokość notatki uwzględnia obramowanie `border-box`. Nowy test odtworzył niedoszacowanie o 2 px; poprawka usuwa różnicę między `scrollHeight` i `clientHeight`, bez wewnętrznego przewijania.

## Jedno edytowalne pole notatek — NIE wdrożono dla połączonych źródeł V2

Zgodnie z wyraźnie dopuszczonym wariantem w poleceniu pozostawiono ochronę źródeł i wykonano pozostałe zmiany. Wspólny, zwijany obszar to nie to samo co jedno swobodnie edytowalne pole całej treści. Obecnie zalecenia są tylko do odczytu, a edycja zmienia wyłącznie dopisek. Nie deklarujemy spełnienia pełnego wymogu jednego pola.

### Analiza istniejącego modelu

- `coachInstructions`: `planVersionId`, opcjonalne `positionId`, `revision`, `text`, `confirmation`, `source`. Potwierdzenie trenerskie jest legalne tylko dla źródła `trainer` (walidacja w `model/training-model.mjs`). Występują instrukcje globalne planu i instrukcje pozycji. Mieszane teksty C1/C2/D2 mają źródło `owner`; nie wolno zgadywać autorstwa poszczególnych zdań.
- `userNotes`: `exerciseId`, opcjonalne `sessionId`, `text`, `origin`, `revision`, `source`. Nie ma jawnego `planVersionId`; bieżący UI rozdziela ogólne wpisy wersji planów za pomocą dotychczasowych stabilnych ID `user:<planVersionId>:<exerciseId>`. Zachowuje dowolne starsze ID, a notatek sesyjnych nie pożycza jako ogólnych. Kolizja ID z innym kontekstem blokuje zapis.
- Historyczne `exercises[].notes` pozostają tekstem bez rozstrzygniętej proweniencji. W V2 są udostępniane jako historyczna treść tylko do odczytu; starszy formularz tekstowy zachowuje swój dotychczasowy zapis. Oryginalne snapshoty sesji zawierają odrębny model źródłowy.
- Niezatwierdzone własne dopiski: dotychczasowe rekordy localStorage `pushpull-note-ui-v1:` z bazą, tekstem, tokenem i osobnym zakresem karty. Różne źródła nie mają automatycznie wybieranego zwycięzcy. Restart, quota, kolizje i jawne anulowanie zachowują istniejące zasady z raportu F. To nadal osobny szkic UI z możliwością pobrania; nie rozszerzono kontraktu backupów ani kolektora v6.

### Dlaczego nie zapisujemy arbitralnie połączonego tekstu

1. Zapis całego pola do `coachInstructions.text` narusza źródło, jego proweniencję i rozdzielenie planu/sesji/użytkownika.
2. Zapis połączonej treści do istniejącego `userNotes.text` bez odrębnego kontraktu widoku powoduje ponowne dołączanie instrukcji przy kolejnym otwarciu lub w starszym UI. Nie ma jawnej informacji, które źródła i rewizje zostały już użyte. Wykorzystanie wolnego tekstu `source.reference` jako ukrytego protokołu nadpisania nie rozwiązuje zgodności czytników ani obsługi zmienionych źródeł.
3. Rozcinanie swobodnie zmienionego tekstu separatorami/po treści nie daje jednoznacznego odwzorowania na oryginalne rekordy. Identyczne fragmenty mogą pochodzić z różnych źródeł; automatyczne usuwanie duplikatów po wartości traci tę informację.

Nie wykonano migracji ani nie skopiowano tekstów do nowej reprezentacji. Źródła, ID, rewizje i powiązania pozostają bez zmian.

### Rekomendowany osobny projekt

Wersjonowana nakładka edycyjna, należąca do użytkownika, z jawnym zakresem `ownerId/exerciseId/planVersionId/sessionId` i referencjami do źródłowych ID, rewizji oraz SHA-256. Zapisuje pełny tekst jednego widoku, zachowując oryginalne instrukcje i stare notatki jako niezależne dowody. Pierwsza projekcja powstaje bez zapisu; zapis następuje dopiero po edycji i potwierdzeniu. Zmiana źródła wymaga jawnego uzgodnienia, bez automatycznego zastąpienia dopisków i bez wybierania zwycięzcy datą. Kontrola CAS obejmuje bazę widoku i referencje źródeł; preimage umożliwia powrót.

Przed wdrożeniem należy zatwierdzić reprezentację, zgodność starych czytników i backup/restore, obsługę wielu kart, niekompletnego zapisu i zmienionego planu. To osobny etap zmieniający kontrakt notatek, nie kosmetyczna migracja wykonywana w tym PR. Nie rozpoczęto Issue #94.

## Zachowane mechanizmy

Bez zmian w schemacie IndexedDB v2, modułach protokołu przyrostowego, CAS, readback, `strict complete`, modelach/źródłach planów, rotacji, wynikach, tonażu, historii, statystykach, Drive oraz kodekach backupów v1–v6 i przywracaniu. Bez automatycznego kasowania danych. Góra aplikacji, wybór treningu, kalendarz, Dane i nawigacja z ikonami pozostają w dotychczasowym wyglądzie. Wejście do Dane nadal nie uruchamia `ensureFull()`.

## Testy i pomiary

Lokalny pełny Node: 219/219 PASS. Lokalna regresja tematyczna: 20 przypadków, 19 PASS i jeden błąd synchronizacji odczytu CSS nowego testu; po oczekiwaniu na koniec rozpoczęcia sesji i sprawdzaniu CSS z automatycznym ponowieniem cały nowy moduł 3/3 PASS. Nie zmieniono asercji danych; oczekiwane kolory i font są sprawdzane dokładnie. Pozostałe 17 scenariuszy obejmowało notatki/quota/kolizje, poprzednie serie 10/10/9, szkice strukturalne po restarcie, back-off, drop, L/P, grupy, plany i aktywację. Pełną regresję końcowego commitu wykonuje workflow PR (219 Node + 211 Chromium/PWA); finalny status jest podany w PR. Testy integralności nie są zastępowane asercjami wizualnymi. Nie wykonano nowego odbioru fizycznego Pixela 9 ani prawdziwego konta Google; testy i profile są syntetyczne, izolowane.

## Pomiary przed/po

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

Zmiany po pomiarach dotyczą wyłącznie testów i raportu; SHA-256 runtime nadal odpowiada opublikowanym pomiarom. Końcowy workflow obejmuje 219 Node i 211 Chromium/PWA; wynik jest podany w PR.
