# PushPull — wyniki kart, szybkie pola i trwałe notatki

Zakres: zatwierdzone polecenie właściciela „prezentacja wyników, uproszczenie edycji i zapis notatek”. Baza: `376ccd34b4713d71751131c5b85681737f110c15` (main po PR #102). Bez Issue #94, migracji danych, zmian backupów lub Drive.

## Zmiany

- **Tylko zwinięta karta**: identyczne rzeczywiste serie kompresują się z zachowaniem dotychczasowych reguł zgodności semantycznej. Różne serie zachowują kolejność. `ResizeObserver` mierzy faktyczny `scrollWidth/clientWidth` tekstu w danej karcie: jeśli cały ciąg się mieści, zostaje w jednej linii z ` | `; w przeciwnym razie każda kompletna seria dostaje własną linię. Drop sam w sobie nie wymusza podziału. `L/P` oraz `L … · P …` pozostają rozróżnialne. Nie dzielimy segmentów jednej serii. Wyjątkowo długi pojedynczy zapis ma lokalne przewijanie własnego wiersza, bez poziomego przewijania strony. Zmiana szerokości/orientacji oraz doładowanie fontu ponawiają pomiar.
- **Szybkie pola**: bez powtarzanego `confirm()`. Zmieniają wspólną wartość danego pola głównych segmentów. Inna wartość historyczna lub indywidualnie poprawione pole pozostaje niezależne. Ochrona działa osobno dla kg/powtórzeń, także gdy szybka wartość po drodze zrówna się z niezależną. Nie zmienia liczby serii, IDs, ról, par, dzieci drop ani drugiego pola. Jawne ujednolicenie wszystkich głównych pól w edytorze przywraca wspólną wartość. Robocze `quickValues/quickLocks` są częścią szkicu, nie wyniku/historycznego modelu. Starszy szkic bez tych pól nadal się otwiera.
- **Back-off**: usunięta etykieta z prezentacji wyników/kompaktowych parametrów V2. Role i odwołania `backoffFromSetId` pozostają w planach i snapshotach; nadal mają znaczenie dla walidacji i decyzji o kompresji. Notatki nie dostają automatycznego tekstu.
- **Notatki**: `saveUserNote` wykorzystuje istniejący przyrostowy writer i jego `change()`. Weryfikuje uwierzytelniony bieżący model, jednoznaczne powiązanie wersja planu–ćwiczenie–wariant, scoped note ID, bazowy tekst/rewizję oraz pełną poprawność nowego bieżącego modelu. Zmienia wyłącznie obiekt bieżącego modelu w metadanych `journal`, jego ścieżkę indeksu/root i wymagane niezmienne obiekty. Nie materializuje pełnej historii ani archiwów, nie przepisuje wyników i snapshotów. Zachowuje nieznane metadane istniejącej własnej notatki.

## Przyczyna opóźnienia notatek

Obsługa każdego formularza notatki trafiała do ogólnego `needsHistory`. Przy selektywnym starcie wykonywała `ensureHistory()`: odczyt i audyt całej historii, walidację i materializację. Następnie mutowała roboczy model i uruchamiała `persist()` → `commit()` → pełne `replaceLive()`, mimo zmiany jednego `userNotes`. Pomiar nie izoluje wpływu samego raw: dotychczasowy `replaceLive()` również odraczał odczyt archiwów. Potwierdzono koszt historii i pełnego zapisu live, a nie błąd PWA lub limit backupu. Koszt rósł z historią, choć zapis serii był już przyrostowy. Kosztowna ścieżka nie wynikała z potrzeby modyfikacji snapshotów ani archiwów.

Samo usunięcie oczekiwania w UI lub cache pełnego odczytu nie usuwa kosztu `replaceLive()`. Samo pominięcie `ensureHistory()` pozostawiałoby niekompletny kandydat pełnego zapisu. Wybrano nową komendę notatki opartą na istniejącym mechanizmie delta metadanych; podział każdej notatki do nowego store nie jest potrzebny.

Po zmianie formularz notatki omija ogólny `needsHistory`; inne operacje wciąż korzystają z odpowiednich audytów. Kandydat powstaje w writerze, a UI otrzymuje małe ACK dopiero po natywnym `complete` transakcji `durability: 'strict'`. Wspólny mechanizm nadal weryfikuje epoch/root/revision CAS, marker, liczniki, uwierzytelnione zależności i readback wszystkich zmienionych rekordów/root. Błąd nie mutuje roboczego `userNotes` ani nie usuwa szkicu. Starszy nieobsługiwany writer nie uruchamia cichego pełnego zastępowania — zgłasza brak aktualnego protokołu i zachowuje szkic.

## Zachowane mechanizmy

IndexedDB v2, schemat i istniejący protokół transakcji; przyrostowy zapis serii/start/finish; obie strony L/P bez dodatkowego ×2; dodawanie/usuwanie/odtwarzanie dropów z PR #102; tonaż, statystyki, rotacja; historia i niezmienne snapshoty; źródłowe instrukcje oraz rozdział własnych notatek; szkice treningu i kończenie ze szkicami; ręczne kopie v1–v6 i Google Drive. Dane nie są resetowane, usuwane ani migrowane.

## Pomiary

| Izolowana baza | Do `strict complete`: mediana / p95 przed → po | Natywna transakcja: mediana przed → po | Do klatki UI: mediana przed → po |
|---|---:|---:|---:|
| 4 sesje, 35 wyników | 7857,4 / 10815,5 → **178,4 / 260,7 ms** | 3453,0 → 82,8 ms | 10615,8 → 266,2 ms |
| 40 sesji, 350 wyników, opaque raw 4 MiB | 35360,6 / 84726,8 → **348,2 / 501,2 ms** | 23734,9 → 209,9 ms | 39349,6 → 440,1 ms |

Mediany etapów (ms), wyznaczone osobno dla każdej próby:

| Baza / wersja | `ensureHistory` | Przygotowanie komendy przed transakcją | Transakcja do complete | Kończenie komendy po complete | Render DOM |
|---|---:|---:|---:|---:|---:|
| 4 sesje / przed | 3268,3 | 705,7 | 3453,0 | 1987,5 | 24,4 |
| 4 sesje / po | 0,0 | 51,7 | 82,8 | 1,9 | 16,6 |
| 40 sesji + raw / przed | 6047,3 | 6221,6 | 23734,9 | 3697,0 | 70,6 |
| 40 sesji + raw / po | 0,0 | 82,9 | 209,9 | 3,6 | 19,5 |

Każdy wariant: n=5 świeżych profili na bazę, Chromium 154.0.8037.57, CPU ×4, szerokość 390 px. Identyczne pliki wejściowe mają SHA-256 w surowych wynikach. Zimny selektywny widok po konwersji; konwersja i pełne kontrole źródła przed/po są poza zegarem notatki. Bez równoległych testów podczas końcowego pomiaru. Wszystkie 20 kontroli pełnego źródła (historia, plany, snapshoty, katalog i archiwa), z pominięciem wyłącznie docelowej notatki, zakończyły się zgodnym SHA-256. Zweryfikowano też dokładną treść i inkrementację rewizji notatki.

Transakcja obejmuje natywne odczyty CAS, kontrolę liczników, zapis, readback i zdarzenie `complete` przy `durability: strict`; nie jest pomiarem samego fizycznego flush dysku. Render to synchroniczna budowa DOM. „Klatka UI” (`clickToPaintMs` w JSON) oznacza drugi callback rAF, czyli okazję pokazania klatki, a nie pomiar fotonu na ekranie. Pozostałe odstępy obejmują kolejkę/feedback frame i logikę aplikacji. Median etapów nie należy dodawać do mediany całości.

p95 jest nearest-rank (maksimum przy n=5), nie estymacją populacyjną Androida. Stara ścieżka wykazała dużą zmienność (do 84,7 s w dużym syntetycznym przypadku). Nie przeliczamy tych liczb na Pixel 9. Mała próba i obciążenie hosta ograniczają wnioski do zaobserwowanych przypadków. Wstępnych prób diagnostycznych uruchomionych przy równoległej regresji nie użyto w tabeli.

Surowe wyniki: [przed](performance/notes-before.json), [po](performance/notes-after.json). Reprodukcja: `python scripts/measure_notes.py --ref 376ccd3 --output <nowy-katalog-przed> --fixtures <katalog-fixtures>` oraz `--ref working --output <nowy-katalog-po>` na identycznych syntetycznych fixtures z istniejącego harnessu `scripts/measure_incremental_write.py` (4/40 sesji, treningowe struktury V2, preimage migracji i raw). Harness buduje niezmienne allowlistowane artefakty z sondami tylko w katalogu testowym. SHA-256 wszystkich oryginalnych assetów jest w wynikach; zgodność assetów „po” z checkoutem sprawdzono przed publikacją.

## Testy i ograniczenia

Weryfikacja lokalna końcowego kodu:

- **249/249 Node — PASS** (`node --test tests/*.test.*`): modele, integralność wyników, L/P, dropy, role, protokół przyrostowy, limity i kopie v1–v6.
- **12 ukierunkowanych scenariuszy Chromium/PWA — PASS**: pięć nowych testów w `test_results_notes`, historyczne indywidualne serie bez potwierdzenia, usunięcie wszystkich L/P/restart/dodanie, podgląd źródła po zakończeniu, osiem identycznych serii i zakończenie offline oraz trzy rzeczywiste aktualizacje PWA (powrót do planu, wiek ostatniego wyniku, asymetryczny szkic). Wcześniejsze testy `userNotes` również potwierdziły przygotowanie notatki przed aktywacją, zmianę planu i ochronę tekstów źródłowych.
- Nowe scenariusze sprawdzają 360/390/412 px i orientację 844×390; rzeczywiste szerokości, jedną linię krótkich wyników i całe serie drop; ochronę indywidualnych pól przy przejściu przez tę samą wartość; restart szkicu; ponowne dodanie pustych serii i brak zmiany dzieci drop.
- Notatki: test blokuje `ensureHistory`, `ensureFull`, `commit`, `export` i pełny getter `value` na ścieżce zapisu; wstrzymana natywna transakcja nie pozwala pokazać sukcesu ani zmienić roboczych notatek; po `complete` potwierdzono `strict`. Abort i uszkodzony readback wycofują zapis, zachowują szkic i pozwalają ponowić offline. Stara karta nie nadpisuje nowszej notatki. Porównano też niezmienne rekordy historii, snapshotów, archiwów, checkpointów i wszystkie wcześniejsze obiekty.
- **20/20 porównań integralności przed/po pomiarze — PASS**, zgodność hashy sond z końcowym runtime — PASS.
- Składnia JS, `git diff --check`, zgodność workera i build produkcyjny — **PASS**. Lokalne wydanie: `722f7ca17917a2c4383d91ce` (artefakt bez sond; nie opublikowano go).

Pierwsze zbiorcze wywołanie lokalne zawierało nieistniejącą nazwę siódmego testu; sześć rzeczywistych testów przeszło. Brakujący test L/P uruchomiono pod właściwą nazwą i zakończył się PASS. Nie pomijano ani nie osłabiano asercji integralności. Zmieniono wyłącznie oczekiwany tekst prezentacji tam, gdzie nowe polecenie zmienia etykiety lub odstępy.

Pełny zestaw Chromium/PWA liczy **242 testy**. Jest weryfikowany w istniejącym workflow `Data safety and mobile regression`, razem z pełnym Node, kontrolą workera i buildem. Aktualny wynik, commit i odnośnik do przebiegu znajdują się w PR; lokalnie wykonano opisane wyżej testy ukierunkowane. Workflow, wyzwalacze i klasy runnerów nie są zmieniane.

Nie testowano fizycznego Pixela 9, Androidowego systemu plików/klawiatury ani prawdziwego konta Google. Nie deklarujemy potwierdzenia czasu 2–3 s na telefonie ani jego usunięcia na urządzeniu. Bieżący model planu pozostaje pojedynczym obiektem: zapis notatki wciąż waliduje/serializuje ten model, ale nie pełną historię. Nie przebadano dowolnie dużych modeli bieżącego planu; zachowano wszystkie wymagane zależności CAS. Rozdzielenie każdej notatki na osobny rekord wymagałoby osobnego projektu i nie należy do tego PR.

Pełny audyt nadal jest wymagany przy operacjach na całej historii, eksporcie i przywracaniu. Notatki szkicowe pozostają lokalnym mechanizmem UI; nie deklarujemy ich kompletnego przechwycenia przez format dowodów wielu kart. Konfliktów nie rozstrzygamy po dacie. Zmiany przygotowane do przeglądu, bez scalenia i ręcznego wdrożenia.
