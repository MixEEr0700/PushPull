# P0 — rzeczywisty zapis wyniku do 1 s: projekt dalszego etapu

## Stan i zakres

Baza: main `2504e5a503a5f0607986fbe29ac1df35aee87c4b`, po scaleniu #76 i #78.
Właściciel zgłosił około 10 s zapisu na fizycznym **Pixel 9**, z aktualnym według
niego Androidem. Numerów Androida/Chrome, wielkości jego bazy ani rozkładu
czasów na urządzeniu nie ustalono. **Nie jest to nasz benchmark telefonu.**
Cel: typowy faktycznie zatwierdzony zapis <=1000 ms, nie samo wyświetlenie
oczekiwania. Nie uznajemy poprawy w chmurowym Chromium za potwierdzenie celu.

W małym PR zmieniają się tylko dwa porównania kompletnego modelu w IndexedDB:
CAS starego modelu oraz kontrola odczytanego nowego modelu. Zamiast dwóch
serializacji canonical na każde porównanie sprawdzamy cały graf JSON, wszystkie
klucze, kolejność tablic i wartości, w tym **dokładny tekst raw**. Pozostaje
stara obsługa canonical dla nietypowych wartości legacy. Nie ma cache ważności,
porównania tylko digest/revision ani pomijania pól. SHA, wszystkie walidatory,
projekcja v3, readback, strict i oncomplete pozostają w istniejącej ścieżce.

To ograniczone usprawnienie jest zaimplementowane. Większego refaktoru buildera
ani nowego protokołu zapisu **nie wdrożono**; wymagają osobnego zatwierdzenia
zgodnie z poleceniem właściciela. Opcjonalny obserwator do pomiaru jest gotowy
poza assetami aplikacji; telefon nie jest podłączony do tego środowiska.

## Co nadal kosztuje czas

Zapis kandydata obejmuje clone i katalog, walidację źródła/katalogu, encode/hash,
budowę pełnego modelu v3, transakcję CAS, przepisanie wszystkich tabel, odczyt
kontrolny i roundtrip, zapis/odczyt pełnego modelu, strict complete, publikację
pamięci, obsługę szkicu i UI. LegacySources/raw zawiera również archiwa.
Nie wszystkie te etapy są fsync lub samym hashowaniem: duża część czasu to
synchroniczne przejścia JS, serializacja, parsowanie, kopie i odbiór IDB.

Szczegółowe liczby oraz mediany/p95 finalnego wariantu są w
[DURABLE_WRITE_P0_REPORT.md](DURABLE_WRITE_P0_REPORT.md). Spany funkcji są
inkluzywne; nie sumujemy ich z rozłącznymi przedziałami etapów.

## Porównanie wariantów

| Wariant | Integralność i kontrakty | Koszt / decyzja |
|---|---|---|
| Pełna równość JSON bez escaped kopii przy CAS/readback | Te same wartości canonical, pełne raw i nieznane pola, te same zapisy i odczyty | Najmniejszy lokalny zakres; wybrany i sprawdzany testami równoważności/tamper |
| Szybszy skaner JSON: indexOf dla końca stringa i szybka ścieżka identycznej reprezentacji liczby | Może zachować duplicate-key, dokładność liczb i escapes; wymaga osobnego dowodu/fuzz dla całej granicy v1–v6 | Prototyp w izolowanym artefakcie, nie w runtime; mniejsza poprawa, szersze ryzyko readerów |
| Dowód walidacji dla całkowicie głęboko zamrożonego grafu | Dopiero po pełnej walidacji i sprawdzeniu niezmienności wszystkich osiągalnych obiektów; żadnego zaufania do samego ID/revision/shallow freeze | Prototyp, nie wdrożony; obiecujący dla powtarzanych snapshotów, wymaga dowodu i testów mutowalnych wejść |
| Pominięcie nieużywanego odczytu starego modelu podczas readback źródła | CAS nadal czyta stary model, nowy model nadal ma własny readback | Wąskie osobne usprawnienie do sprawdzenia; nie usuwa dominującej projekcji |
| Różnicowy zapis w obecnych tabelach, nadal z pełnym readback | Ten sam format rekordów; cache poprzednich wierszy musi być związany ze zweryfikowaną rewizją, usunięcia serii i błędne obce wiersze muszą być wykrywane | Może ograniczyć koszt clear/add dużej historii legacy; pełny odczyt/weryfikacja i mostek pozostają, więc sam nie rozwiązuje celu |
| Worker przy zachowaniu całego obecnego protokołu | Może odciążyć UI, ale nie usuwa pracy ani czasu strict complete; dochodzi transport/kopie | Sam worker nie spełnia celu trwałego zapisu <=1 s |
| Zapis przyrostowy / manifest zamiast odbudowy całego mostka | Wymaga nowego protokołu integralności, współistnienia starszych kart i odzyskiwania | Duża zmiana; nie mieści się w obecnym zakazie migracji/zmian kontraktów |

Wstępne porównanie prototypów było pojedynczą próbką V2 4 + raw 4 MiB,
CPU x4, z profilerem (nie seria p95): pełny czas około 2038 ms bazowo,
1685 ms z samą równością modeli, 1582 ms z dodatkowym szybszym parserem,
1465 ms z równością i prototypem dowodów niezmienności zamiast parsera.
Parser zajmował odpowiednio około 190/195/85/195 ms. To wskazówka kierunku,
nie zweryfikowana gotowość prototypów ani porównanie fizycznego telefonu.
Prototypy nie są częścią aplikacji i nie posłużyły jako zamiennik pomiarów
finalnej implementacji.

## Prywatny profil reprezentatywnego Pixela — po stronie właściciela

Bez czyszczenia, reloadu z narzędzia, zmiany origin lub odczytu/eksportu bazy:

1. Na telefonie otworzyć zwykłą aplikację i własny formularz treningu. Nie
   wykonywać automatycznych syntetycznych zapisów w bazie właściciela.
2. Opcjonalny [snippet DevTools](../scripts/pixel_write_probe.js) można uruchomić
   w konsoli tej strony przez zdalny Chrome DevTools/USB. Nie jest assetem PWA.
   Obserwuje istniejące operacje, nie inicjuje requestów IDB ani sieciowych,
   nie czyta wyników requestów, formularzy, tokenów, ID ani raw. Nie zmienia UI.
3. Po jednym normalnym zatwierdzeniu odczytać
   `PushPullWriteProbe.samples()`. Rozdziela czas przed transakcją, transakcję,
   model-get latency, model-put, natywne SHA (czas i liczba bajtów, bez treści),
   strict complete i odblokowanie UI. Można
   skopiować wyłącznie agregaty przez
   `copy(JSON.stringify(PushPullWriteProbe.samples(), null, 2))` w DevTools.
4. `PushPullWriteProbe.stop()` przywraca hooki; reload także usuwa obserwator,
   ale narzędzie samo nie odświeża strony. Bufor jest tylko w pamięci, max 20
   operacji. Dłuższe serie zbierać partiami. Nie przesyłać raw/backupów lub
   pełnego heap/performance trace zawierającego prywatne informacje.
5. Do SLO brać tylko `status: complete` i `durability: strict`.
   `no-history-complete`/`aborted` nie oznacza zapisu. Wykonywać jedną operację
   naraz; snippet nie zapewnia korelacji z innymi stronami/queued plan importem.
   UI-ready jest callbackiem DOM, nie fizycznym pomiarem odmalowania pikseli.

Snippet nie odsłania prywatnych etapów JS w closure. Do ich rozdzielenia na
urządzeniu potrzebny jest lokalny profil CPU bez screenshots/heap lub osobny
opt-in build diagnostyczny zbierający wyłącznie stałe etykiety i czasy. Nie
wdrożono takiego buildu ani nie podłączono telefonu w tym zadaniu.

## Etap B do zatwierdzenia: jedna przygotowana rewizja, bez nowego formatu

Cel: usunąć powtarzanie pracy, zachowując istniejące bajty/semantykę modelu.

- Prywatny builder tworzy jeden odłączony, portable kandydat. Żadna referencja
  do mutowalnego formularza nie może zmienić kandydata po rozpoczęciu await.
- Pełna walidacja JSON i relacji wejścia pozostaje. Synchronous batch może
  ponownie wykorzystać dowód wyłącznie dla tego samego głęboko niezmiennego
  grafu; płytki Object.freeze, ID oraz globalny sequence nie są dowodem.
- Rozdzielić wewnętrzne składanie payloadu z już zwalidowanej wartości od
  publicznego readera niezaufanego tekstu. Uniknąć ponownego parsowania
  JSON.stringify własnego portable kandydata, **nie** parsowania przy imporcie.
- Pełny raw źródła nadal powstaje z tego samego kandydata i zachowuje wszystkie
  archiwa/metadane. Canonical, SHA i końcowy v3 muszą być zgodne z readerem
  wcześniejszej aplikacji. Każda nieznana właściwość musi przejść bez strat.
- Opcjonalny cache serializacji niezmiennych archiwów ma być ograniczony,
  odrzucalny bez usuwania danych i oparty na pełnej treści/niezmienności,
  nie nazwie ani dacie. Budżet ustalić po pomiarze peak memory na telefonie;
  nie przenosić całego opóźnienia na startup jako ukrytego „przyspieszenia”.
- CAS sprawdza rzeczywisty stary model/revision w tej samej readwrite tx.
  Wszystkie zmienione i zależne dane oraz nowy model mają readback.
  Sukces nadal dopiero po strict complete; szkic zachowany do tego momentu.
- W razie błędu/quota/abort/zmiany karty: stara rewizja i szkic pozostają,
  stan oczekiwania znika z czytelnym błędem; bez publikacji kandydata w UI.

Docelowy budżet do zweryfikowania na urządzeniu, **nie prognoza uzyskanego
wyniku**: przyjęcie akcji/klatka 50 ms, przygotowanie i walidacja 250 ms,
serializacja/hash 150 ms, CAS + zapis/readback + strict 450 ms, publikacja
szkicu/UI 100 ms. Łącznie 1000 ms, z strict complete przed komunikatem sukcesu.
Jeśli etap nie mieści budżetu przy rzeczywistej wielkości danych właściciela,
nie wolno wyłączyć walidacji lub nazwać samego pending „zapisem”.

Przy ewentualnym różnicowym writerze trzeba osobno dowieść zachowania
kolejności/ID, usuwania zastępowanych serii, nieznanych metadanych oraz
wykrywania zmienionych/osieroconych wierszy. Pełny import/restore powinien
pozostać na istniejącej ścieżce do czasu osobnej weryfikacji. Nie wdrożono
takiej zmiany granularności zapisu w małym PR.

To większy refaktor walidacji/buildera, nie część małego PR. Nie wolno użyć
opcji `skipValidation` ani otwartego publicznego tokenu zaufania. Testy mają
wykazać identyczność danych/digest i odrzucania nieprawidłowych wejść, dowolnej
zmiany nieznanego pola/raw, mutacji po await, shallow freeze i zmian innych kart.

## Warunki odbioru i ryzyko dalszej architektury

Syntetyczne porównanie przed/po ma obejmować identyczne źródła i środowisko,
małe/duże legacy, realne struktury V2, wielomegabajtowe ASCII/Unicode/escaped
archiwa, cold-first oraz warm zapisy, medianę/p95 i obserwowany max.
Na reprezentatywnym Pixel 9 potrzebna jest oddzielna seria zwykłych zapisów
(nowe wyniki i korekty, online/offline, także pierwszy zapis po uruchomieniu),
po potwierdzeniu wersji aplikacji. Cel: <=1000 ms dla badanych typowych zapisów,
nie tylko mediany. Nie jest to gwarancja hard real-time przy dowolnym obciążeniu
Androida; odstępstw nie wolno ukrywać pod średnią lub samym komunikatem UI.

Jeżeli ten etap nie mieści celu na rzeczywistej wielkości bazy, trzeba osobno
zaprojektować zapis przyrostowy i manifest niezmiennych części. Dotychczasowy
`training-model-v1` zawiera pełne raw i jest zgodny z rewizją źródła; pozostawienie
starego modelu z nową rewizją uszkodziłoby dzisiejszą weryfikację/recovery.
Dodanie manifestu nawet w istniejącym store meta jest zmianą kontraktu zapisu,
a nie „brakiem migracji” tylko dlatego, że VERSION pozostałby 1.

Takie rozwiązanie wymaga osobnej zgody na kontrakt, bezstratne współistnienie
checkpointu i nowych rekordów, zachowanie starych kart/PWA lub jawne bezpieczne
zablokowanie starego writera, pełny eksport/import v1–v6 i zachowanie preimage,
rollback przy quota/przerwaniu, obsługę aktualizacji i dodatkowego miejsca na
checkpoint. Nie wolno usuwać starej historii/archiwów. Aktualny zakaz migracji
wyklucza jego implementację w tym zadaniu. Nie rozpoczęto Issue #61, przywracania
v4/v6 ani zmian Google Drive.
