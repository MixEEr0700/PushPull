# Issue #71 — rzeczywiste źródła szkiców, observed-origin

Baza main `4230ca36b7b709de341d1421e275a8142169eb71`, scalony PR #70 potwierdzony przed implementacją. Plan i dokumentacja v6 przeczytane. Nie zmieniono formatu v5/v6, schematu DB, zapisu szkiców, tokenów/CAS, przywracania ani Drive. Nowy inspektor `inspectDraftEvidence` jest wyłącznie dodatkowym czystym API istniejącej walidacji kodeka v6.

## Źródła i odczyt

`database.readDraftObservation()` wykonuje jedną readonly transakcję: root `meta/state` (rewizja) i zakres kluczy `workout-draft:`. Pobiera do 1025 rekordów i odmawia ponad 1024 zamiast przycinać. Nie odczytuje archiwów ani całego modelState/ustawień Drive. Transakcja używa dotychczasowego helpera i jego scope ALL (operacje odczytu tylko meta); nie dodaje blokady writerów. Wartości draftów nie są filtrowane przez shape/resume ani scalane.

`readBuffer()` czyta tylko klucze prefixu `pushpull_workout_draft_v1:` i dokładne raw. Nie parsuje ich do „najnowszej wersji”. Zmiana długości listy lub zniknięcie klucza przerywa próbę jako niestabilną. Stała długość nie dowodzi braku zmian: całe wektory raw są porównywane pomiędzy obserwacjami. Nigdy nie czytamy innych wartości localStorage.

`openDrafts().readEvidence()` odczytuje bez zmiany active map: record, binding, durableToken i parent dla każdego aktywnego stanu capture. Nie używa merged records/reload ani flush, take, confirmed, discard, removeDraft lub clearBuffer. Odczyt dotyczy rzeczywistej pamięci szkiców przechwyconych przez istniejące zdarzenia edytora, także gdy IDB i/lub bufor nie utrwaliły zapisu. Nie jest przechwytywaniem dowolnego DOM/IME przed obsłużeniem zdarzenia input ani prywatnych closure starszych kolejek. Samo otwarcie formularza bez edycji nie tworzy nowego szkicu. Stan wznowiony z record:null zachowuje parent/binding w dowodach i może zostać sklasyfikowany przez codec jako quarantine; nic nie jest wymyślane lub nakładane na historię.

## Kolektor i stabilność

`collectDrafts({database,getMemory,storage,peers,signal,limits,attempts})`:

1. Odczytuje IDB, LS, pamięć oraz odpowiedzi innych współpracujących kart.
2. Waliduje całe źródła istniejącym inspektorem v6 i odłącza obserwowane wartości. Zachowuje duplikaty, konflikty, niepoprawne raw i wszystkie dostępne wersje.
3. Oddaje sterowanie przez macrotask i wykonuje drugi pełny odczyt.
4. Porównuje wszystkie klucze/wartości/tokeny/sequence i zestaw respondentów oraz rewizję historii. Zmiana samego draftu wykrywana jest niezależnie od historyRevision.
5. Domyślnie do 2 prób (API dopuszcza 1–3). Po wyczerpaniu odmowa, bez częściowego evidence lub pliku. Brak IDB/LS/pamięci to błąd źródła, nie pusty sukces. Utrata znanego respondenta to odmowa.

Wynik: evidence zgodne z v6, classification z tego samego walidatora, capture o scope observed-origin i consistency observed-stable, coverage i liczbowe diagnostics. Nie ma obietnicy pełnej kopii urządzenia. Próby nie zwiększają rewizji, nie kasują niczego i nie potwierdzają zapisów. Abort przerywa również oczekiwanie na nieodpowiadający readonly adapter; bazowa operacja I/O może dokończyć się później, bez zapisu lub raportu. Synchroniczny clone/skaner/hash nie jest natychmiast przerywany.

Obecny kolektor NIE zbiera pełnej historii do nowego pliku v6: zwraca rewizję obserwowaną z IDB oraz dowody szkiców. Połączenie z przyszłym snapshotem historii musi zapewnić zgodny punkt odczytu/ponowną weryfikację, nie może bezkrytycznie użyć starego cache database.export(). Nie podłączono nowego downloadu/restore.

## Wiele kart bez ingerencji w write-path

Nowy kanał `pushpull-draft-observer-v1` służy wyłącznie do żądania/odpowiedzi z pamięci. Każda działająca aktualna karta ma efemeryczny ID. Brak trwałego rejestru, zmiany zapisów lub blokowania input. IDB i LS są wspólne dla originu; przez kanał zbieramy dodatkową pamięć respondentów, nie ponownie scalany widok odzyskiwania.

Domyślne okno odpowiedzi 60 ms na odczyt (API: 1–500 ms); najwyżej 32 respondentów. Nieobecność odpowiedzi NIE oznacza braku innych kart. Stara, uśpiona, nieobsługująca BC, otwarta po obserwacji lub niereagująca karta ma stan nieznany. `coverage.otherTabs='unknown'` zawsze pozostaje jawne, nawet przy zerowej liczbie respondentów. Jeśli respondent widziany w pierwszej rundzie znika w kolejnej, bieżąca kolekcja nie pomija go i odmawia. Więcej respondentów lub nieodczytywalna pamięć znanego respondenta to również odmowa. BC niedostępny przy inicjalizacji nie blokuje uruchomienia aplikacji; odczyt lokalny pozostaje observed-origin bez inwentaryzacji kart.

Dwa zgodne odczyty NIE są globalną transakcją IDB+LS+pamięć. Nie wykrywają każdej zmiany ABA lub edycji w nieznanej starej karcie. Nie deklarujemy complete-device ani snapshotu całego urządzenia.

Silniejszy protokół wymaga osobnej decyzji: wspólny protokół wszystkich writerów, epok/barier i zasad dla starszych/nieodpowiadających kart; wpływ na natychmiastowy bufor input i kolejki/CAS oraz migrację zachowania otwartych stron musi zostać przedstawiony przed zmianą. Sam Web Lock eksportera nie wystarczy. Tego etapu nie implementowano.

## UI, prywatność i pamięć

Nowy przycisk w Dane: „Sprawdź szkice do kopii (testowo)”. Pokazuje tylko liczby źródeł/konfliktów/kwarantanny i respondentów oraz jawne ograniczenie pokrycia. Nie wyświetla raw, ID, tokenów ani etykiet z danych. Nie pobiera kopii i nie zapisuje wyniku. Anulowanie dostępne podczas zbierania. App przechowuje po zakończeniu jedynie niewielki raport, nie całą kolekcję.

Kod kolektora i v6 dodano do allowlisty i precache, aby obserwacja działała po przeładowaniu offline. Dotychczasowe kontrolki kopii/restore nie są podmieniane. Model/Matrix/Drive i formaty pozostają bez zmian. Historyczne harnessy otrzymują nowe pliki jako nieużywane zasoby, bez zmiany starego kodu aplikacji i asercji.

Limity odziedziczone z v6 obejmują globalnie wszystkie źródła (także peerów), ich token JSON, liczbę tożsamości i kwarantannę. Nie limitujemy każdego peera osobnym pełnym budżetem i nie łączymy dowolnej liczby odpowiedzi. Nie podniesiono limitów. IDB root może zawierać duży legacyRaw, a silnik musi materializować odczytany rekord; brak obietnicy stałego RAM. BC nie jest granicą bezpieczeństwa wobec złośliwego kodu tego samego originu. Po stronie kolektora są bounded odpowiedzi/rozmiary, bez gwarancji ograniczenia pamięci samego IPC silnika przeglądarki.

## Walidacja

7 nowych Node: zachowanie osobnych źródeł/konfliktów/raw, brak flush/reload/write API, zmiana draftu bez zmiany rewizji, retry/refusal, oddzielne niedostępne źródła, znany respondent bez odpowiedzi, >32 peerów, abort także podczas bezterminowego oczekiwania, limity i niedostępny BroadcastChannel.

4 nowe Chromium w syntetycznych profilach z rzeczywistą IndexedDB/LS/pamięcią:

- Natywne V2 i dwie edytujące strony tworzą niezależne ID; kolektor UI odczytuje pamięć obu; pełne store i LS identyczne przed/po. Telefon 390×844, reload offline, zamknięcie innej strony, jawne unknown.
- Legacy edytor i bufor po symulowanym błędzie writeDraft; zachowanie nieukończonego kg `1,` w rzeczywistej pamięci modułu oraz bufora, bez zmiany store podczas odczytu.
- Rzeczywista modyfikacja LS między rundami -> 2 próby i odmowa; abort; IDB bez zmian. Zmiany LS w tym scenariuszu wykonuje wyłącznie zasymulowany writer testu.
- Osobny renderer old-space 128 MiB, 500 k znaków opaque bufora + 4 MiB raw archiwum w store backups, offline; kwarantanna zachowana, pełne porównanie wszystkich store/LS przed i po. Kolektor nie odczytuje archiwów.

Pełne Node/Chromium/PWA offline/CI, kompilacja artefaktu i hash SW: wyniki w PR. Nie testowano fizycznego Androida ani danych właściciela, szczytowego RSS, każdego starego/nieodpowiadającego typu karty lub silnego globalnego snapshotu. Testy nie są dowodem kompletności danych urządzenia. Nie implementowano produkcyjnego restore, Google Drive, zmian kontraktu v6, migracji DB ani Issue #61.
