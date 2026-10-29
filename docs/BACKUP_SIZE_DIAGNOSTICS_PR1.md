# Lokalna diagnostyka rozmiaru — PR 1 po #105

Baza: `main` `44c1ce6`. Przeczytano plan nadrzędny, AGENTS.md i raport Issue #54. Pliku `PushPull_Specyfikacja_Kopii_i_Dane_po_PR105.md` nie ma w udostępnionym checkoutcie; nie zakładano dostępu do Library. Zakres wyznaczają wymagania właściciela w zleceniu PR 1.

W Dane → Opcje zaawansowane dodano „Sprawdź rozmiar kopii”, anulowanie oraz pobranie małego anonimowego raportu. Główne cztery działania, eksportery, import/restore, Drive, schemat i writery IndexedDB pozostają bez zmian. Nie usuwano danych ani nie spłaszczano archiwów.

## Co dokładnie mierzymy

Pomiar dotyczy **kompletnego źródła JSON v2, z którego obecny eksporter buduje kopię**, oraz osobnego inwentarza rekordów protokołu IndexedDB v2. Raport **nie podaje rozmiaru gotowego eksportu v3, skompresowanego v4–v6, multipart POST ani fizycznego pliku IndexedDB**. Projekcja v3 zawiera dodatkowe reprezentacje; ten etap nie buduje jej, nie zmienia formatu i nie przedstawia sumy źródła jako gotowego pliku.

Rozłączny podział `sourceBytes`:

- `history`: kompletne tablice sesji i wyników oraz historia zmian `data.changes`;
- `snapshots`: kompletna tablica `trainingJournal.sessionSnapshots`, łącznie z każdym osadzonym modelem;
- `archives`: kompletna tablica archiwów, wraz z metadanymi, raw/null i rozszerzeniami;
- `model`: pozostałe wartości pól dziennika, w tym ćwiczenia, notatki, bieżący model, pakiety planów, aktywacje i stan bieżący;
- `catalog`: kompletny katalog;
- `other`: pozostałe wartości pól źródła, także nagłówek formatu;
- `structure`: klucze i kontenery metadata źródła/data/journal, nieprzypisane do powyższych kompletnych sekcji.

Suma siedmiu składników równa się `sourceBytes.total`, czyli liczbie bajtów UTF-8 `JSON.stringify(source)`. Nie sumujemy wielokrotnie tej samej sekcji. Nieznane rozszerzenia również są liczone.

Oddzielnie pokazujemy powtórne użycia **identycznych obiektów po referencjach protokołu**. `uniqueReferencedObjects + repeatedReferencedObjects + referenceEnvelope = sourceBytes.total`. To dowód powielania reprezentacji przy materializacji, nie liczba dodatkowych treningów ani dowód duplikatów wewnątrz różnych raw. Zagnieżdżone archiwa pozostają nieinterpretowanymi tekstami.

`sourceAsJsonString` i `sourceAsJsonStringAgain` to dokładne rozmiary zakodowania całego kompaktowego źródła jako tekstu JSON, kolejno raz i dwa razy. Osobne pola podają przyrost każdej warstwy. Ułatwia to ocenę narzutu źródła w kopii i zewnętrznym opakowaniu. **Nie są to rozmiary kompletnych plików v3/Drive.** `sourcePretty` odpowiada `JSON.stringify(source, null, 2)`, a `sourceFormattingOverhead` jest samą różnicą względem kompaktowego źródła. Żaden taki duży string nie jest produkowany przez diagnostykę.

`storedBytes` to osobna, rozłączna suma rozmiarów JSON wszystkich rekordów dziewięciu store’ów protokołu: aktywne obiekty, zachowane wcześniejsze obiekty/kotwica, checkpointy ratunkowe i pozostałe wiersze/indeksy/root. Każdy fizyczny rekord liczony jest raz. Tego inwentarza nie dodajemy do źródła. Nie obejmuje on osobnych starszych tabel, ustawień/szkiców `meta` ani localStorage; checkpointy mogą zawierać ich historyczne migawki. Nie porównujemy ich jako dodatkowych unikalnych treningów.

Liczniki sesji, wyników, snapshotów i archiwów pochodzą z aktywnych kolekcji. Wersje planów modelu deduplikujemy po ID w bieżącym modelu, snapshotach i pakietach. Plany i wersje katalogu są osobnymi licznikami o innym znaczeniu; nie są do nich dodawane.

## Odczyt, pamięć, spójność i prywatność

- Osobny moduł Worker otwiera istniejącą bazę bez wersjonowania i bez wywołania fasady aplikacji, konwersji, eksportera lub `ensureFull()`. Każda transakcja jest `readonly`. Nie czyta localStorage, ustawień Drive ani szkiców. Brak żądań zewnętrznych.
- Odczyt po jednym rekordzie; brak `getAll()` historii/archiwów i brak pełnej materializacji. Zachowywane są małe wiersze referencji, profile liczbowe i zbiory referencji. Opaque/raw nie jest parsowane. Analiza semantyczna planów dotyczy tylko małych katalogów/modeli/pakietów.
- Licznik UTF-8/escape uwzględnia pary i samotne surogaty oraz znaki sterujące. Dla materializacji sumuje profile zamiast składać JSON. Wcięcia liczone są z tokenów, bez budowy tekstu.
- Progi odmowy: 250 000 rekordów, 64 MiB największego obiektu, 64 MiB łącznie checkpointów, 8 MiB pojedynczego obiektu analizowanego semantycznie, 120 s. Próg checkpointów jest sprawdzany z budżetu root pomniejszonego o zweryfikowane rozmiary wszystkich obiektów **przed pobraniem checkpointu**. Test sprawdza brak takiego odczytu po odmowie.
- To progi ostrożności, nie zmierzony limit RAM Androida. Natywny IndexedDB musi sklonować pojedynczy rekord w całości; nie daje dostępu do fragmentów pola tekstowego. Czas GC, pamięć silnika, duża liczba małych referencji i inne karty pozostają poza gwarancją. Za duża baza otrzymuje komunikat braku możliwości pomiaru, bez częściowego raportu i bez automatycznego podnoszenia limitów.
- Krótkie transakcje kończą się przed liczeniem. Nie utrzymujemy wielosekundowego odczytu blokującego writery. Początkowa rewizja musi odpowiadać rewizji UI; końcowy root musi być identyczny z początkowym. UI ponownie sprawdza rewizję/błąd przed publikacją i pobraniem. Liczby z przerwanego/nieaktualnego pomiaru nie są publikowane.
- Anulowanie kończy worker; numer/tożsamość operacji blokuje spóźniony wynik. Nawigacja pozostaje dostępna. Zakończenie podmienia tylko sekcję diagnostyki, nie formularze ani cały ekran.
- Worker zwraca wyłącznie allowlistę liczników bajtów/liczebności i względnych czasów w ms. Raport <8 KiB. Brak dat, nazw, ID, rewizji/root/hash, wyników, notatek, tokenów i raw. Błędy mają stałe kody i komunikaty; nie pokazują treści wyjątku. Plik raportu nie jest kopią do przywracania.
- To inwentarz bajtów, **nie audyt integralności całej kopii**, walidacja odzyskiwalności lub poświadczenie poprawności wszystkich zachowanych archiwów. Dotychczasowe walidatory pozostają obowiązkowe przy eksporcie/importowaniu.

## Testy i pomiary

Testy Node porównują wszystkie profile z niezależnymi natywnymi `JSON.stringify` / UTF-8 dla małych fixture’ów, Unicode, kodowania wielokrotnego oraz 400 sesji z deduplikowanymi modelami snapshotów. Sprawdzają rozłączność sum, brak zmian wejścia, brakujące źródło, przerwanie, zmianę rewizji, błędy, limity i ścisłą allowlistę raportu. Osobna próba licznika działa z limitem starej generacji V8 64 MiB i wylicza wirtualne kodowanie >200 MB; nie jest pomiarem całego Workera/Androida.

Lokalne Chromium: **19/19 PASS**. Nowe cztery przypadki obejmują offline/PWA, 360/390/412 px, porównanie wszystkich rekordów i localStorage przed/po, brak pełnych metod eksportu fasady, anulowanie/spóźniony worker, konflikt rewizji, awarię workera bez ujawnienia wyjątku i duży opaque archive. Dużą bazę porównano SHA-256 wszystkich rekordów wszystkich store’ów przed/po. Pozostałe przypadki chronią cztery działania Dane, poprawki Drive B1/B2, build/allowlistę, aktualizację PWA i offline w podkatalogu.

Profil syntetyczny: Chromium/Linux, 11 sesji, 46 wyników, 6 snapshotów, 4 archiwa; strona z CPU ×4, worker w oddzielnym kontekście. Pomiar nawigacji n=5. Nie uruchamiano drugiego lokalnego Chromium podczas pomiaru. Dane: [anonimowy wynik](performance/backup-size-diagnostics.json).

| Miara | Wynik |
| --- | ---: |
| Rozłączne źródło | 66 429 506 B |
| Z tego archiwa | 65 817 856 B |
| Źródło zakodowane jako tekst raz | 118 059 099 B |
| Źródło zakodowane jako tekst dwa razy | 221 318 285 B |
| Sam narzut formatowania źródła | 507 963 B |
| Rekordy protokołu (osobny inwentarz) | 117 941 763 B |
| Pełny pomiar | 1 252 ms |
| Reakcja na nawigację: mediana / p95 | 24 / 27 ms |
| Najdłuższe zaobserwowane zadanie głównej strony | 55 ms |

P95 przy n=5 to maksimum próby, nie statystyczna gwarancja urządzenia. CPU ×4 dotyczy emulacji strony; nie stanowi pomiaru fizycznego procesora Pixela ani równoważności throttlingu workerów. Odciski baz/orakle w testach mogą alokować pełne reprezentacje; produkcyjna diagnostyka nie korzysta z tych orakli. Nie zmierzono całkowitego szczytu RAM urządzenia.

Pełne lokalne Node: **257/257 PASS**, 34,94 s. Izolowany licznik: wirtualne 220 200 988 B, 316 ms, maksymalny RSS procesu 62 386 176 B przy limicie V8 old-space 64 MiB. Build produkcyjny i zgodność hashy service workera PASS (release `b252bdcae5536cf39cf2eab7`). Wynik istniejącego pełnego CI na końcowym commicie znajduje się w opisie PR. Nie powtarzano wcześniejszych kosztownych analiz Issue #54 ani nie zmieniano workflow.

## Odbiór na Pixelu 9 i ograniczenia

Brak fizycznego testu na Pixelu 9 i pomiaru rzeczywistej bazy właściciela. Po zatwierdzeniu i normalnej aktualizacji PWA: otworzyć opcje zaawansowane, uruchomić pomiar, sprawdzić nawigację i anulowanie, wykonać nowy pomiar offline oraz pobrać mały raport. Udostępnienie tego pliku nie wymaga wysyłania kopii treningowej. Przy odmowie pamięci/czasu nie ponawiać przez automatyczne podnoszenie progów ani nie kasować danych; stan pozostaje bez zmian.

Nie oszacowano czasu uploadu, kompresji, pełnego v3, pojemności dysku ani wymaganej pamięci importera. Nie zmniejszono istniejących kopii >200 MB. Rozwiązanie zagnieżdżonych archiwów, nowe formaty i semantyka odzyskiwania należą do oddzielnych etapów wymagających decyzji właściciela. Brak scalenia i ręcznego wdrożenia.
