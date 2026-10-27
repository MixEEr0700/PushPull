# Etap E — szybki start i komendy sesji (Issue #88)

Baza: PR #87, `4aea982d4f77257b3836ef11a76d12f444cbe5ea`.
Łańcuch pozostaje niescalony: #83 → #84 → #85 → #87 → E.
Nie zmieniono CSS, Matrix, Google Drive ani formatów kopii v1–v6.
Poniższe pomiary dotyczą izolowanych danych syntetycznych Chromium/Linux,
CPU ×4, ekranu 390×844. **Nie są wynikami fizycznego Pixela 9.**

## Potwierdzona przyczyna

Zachowane profile D (`docs/performance/startup-p0-*.json`) rozdzielają zwykły
start od konwersji i certyfikacji. Czasy inkluzywne, mediany ms; nie sumować:

| Etap D | 40 sesji / raw 4 MiB | 400 sesji / raw 4 MiB |
|---|---:|---:|
| readTraining: odczyt + pełna weryfikacja live | 762 | 4929 |
| materializeTraining: Merkle, obiekty, graf | 591 | 3593 |
| validateSource: walidacja relacji | 289 | 1553 |
| facade openDatabase (w tym powyższe) | 851 | 5717 |
| odtwarzanie szkiców | 4 | 16 |
| render (w tym main) | 37 | 119 |

DOM nie wyjaśniał wielosekundowego startu. D unikał już raw/checkpointów,
lecz czytał wszystkie sesje, wyniki, snapshoty, węzły Merkle i zbiory ID.
Nie powtórzono analiz PR #79/#81, konwersji v1 ani znanego limitu rekordu
v1 dla 400 sesji. Etap E mierzy zwykły start po D i osobno instalację indeksu.

## Kontrakt indeksu

Root protokołu 2 otrzymuje opcjonalne `runtime`:
`{version:1,indexRoot,sourceRoot}`. `sourceRoot` musi równać się głównemu
`indexRoot`; wszystkie pola są objęte SHA-256 root/epoch/revision.
Schemat IndexedDB i object stores pozostają w wersji 2. Nowe obiekty i
węzły są content-addressed i uwzględnione w limitach allocation.

Oddzielne drzewo AVL zawiera klucze:

- `info`: max sequence, ostatnia zakończona sesja, snapshoty podglądu
  rzeczywiście zgodne z bieżącymi parametrami źródłowymi;
- `context/exerciseId`: najnowsze główki per wariant/plan/jednostka/baza kg
  oraz dokładny wiek zmiany wyniku, z tą samą semantyką co pełny oracle;
- `history/exerciseId`: małe deskryptory pomiaru i kontekstu; odczyt przy
  zmianie tego ćwiczenia, nie podczas uruchamiania;
- `global/resultId`: właściciel każdego globalnego ID wyniku;
- `pair/sessionId/exerciseId` i `session/sessionId`: dokładne powiązania.

Nie porównujemy nieporównywalnych wariantów ani konwencji. L/P, drop,
back-off i nieustalony pomiar zachowują dotychczasową semantykę. Wyliczenie
korzysta z istniejącej funkcji `comparison`, a testy porównują indeks z
`resultChangeAge` na pełnej historii. Kolizje obejmują również niewczytane
wyniki. Usunięte z korekty ID są usuwane z aktywnego indeksu; stare
niezmienne obiekty/węzły nadal pozostają w bazie jako dowód rewizji.

## Odczyt, zapis i granica zaufania

Zwykły reader odczytuje metadata/plan, aktywną sesję, niezbędne główki
wyników, ich snapshoty i uwierzytelnione ścieżki Merkle. Sprawdza root,
marker, SHA obiektów/węzłów, relacje wymaganych snapshotów/wyników i
liczności stores. Nie używa `getAll` historii, indeksu, raw ani checkpointu.
Karty filtrują główki według faktycznego kontekstu, bez zgadywania historii.
Wszystkie jednostki bieżącego planu są przygotowane do dotychczasowej
synchronicznej nawigacji Matrix.

Kalendarz/historia/statystyki doczytują i walidują pełny graf live.
Zwykła edycja pełnego modelu odmawia, jeżeli caller nie wczytał historii
**przed** przygotowaniem mutacji. Dane/eksport/preimage/import wymagają
pełnego audytu, obejmującego raw, checkpointy i semantyczne przeliczenie
całego indeksu z pełnego źródła. Bulk edits przebudowują indeks atomowo.
Historyczne szkice wymagające innej sesji powodują pełny odczyt live przed
oceną zgodności — brak danych nie jest przedstawiany jako konflikt szkicu.

`saveResult`, `startSession`, `finishSession` przygotowują hashe poza IDB,
sprawdzają root/epoch/revision, wymagane obiekty i ścieżki, aktualizują
zmienione rekordy i oba drzewa w jednej transakcji `durability:strict`.
Readback odbywa się przed jej końcem, a publikacja i sukces dopiero po
natywnym `complete`. Powtórna komenda nie tworzy drugiej sesji. Zakończenie
nie omija szkiców ani reguł rotacji przy zmianie planu w trakcie sesji.
Nie użyto `reload()` ani `flush()` jako dowodu trwałości treningu.

Indeks powstaje wyłącznie z uprzednio zweryfikowanego grafu live.
Backup nie dostarcza zaufanego indeksu. Skrócony start jest dowodem
wymaganych fragmentów, a nie pełnym audytem każdego nieczytanego bajtu
historii/archiwów. Pełny audyt wykrywa również indeks poprawnie hashowany,
ale semantycznie niezgodny ze źródłem. Złośliwe przepisanie całej bazy wraz
z ponownym wyliczeniem wszystkich hashy nie jest chronione podpisem ani
zewnętrznym kluczem — ten kontrakt pozostaje niezmieniony.

## Instalacja, odmowa i rollback

Baza D bez indeksu: jednorazowy zweryfikowany odczyt live, wyprowadzenie
indeksu, strict CAS/readback i aktywacja nowego root. Sama instalacja indeksu
nie zmienia rewizji dziennika ani obserwacji szkiców: nie zmieniła treningów.
Zmiana pełnego root nadal odrzuca każdego wcześniej przygotowanego writera.
Oryginalne wiersze,
archiwa, checkpointy, rewizje i modele pozostają. Równoległa instalacja
nie nadpisuje nowszego root. Przerwanie/quota pozostawia poprzedni root;
ponowne otwarcie może powtórzyć przygotowanie bez częściowego indeksu.
Stara konwersja v1 → v2 i jej checkpoint/wznowienie pozostają oddzielne.
Nie resetujemy danych testowych automatycznie.

Uszkodzony indeks: odmowa treningu/zapisu, bez cichej przebudowy. Zachować
pobranie diagnostyczne całej bazy. Świadoma ścieżka odzyskania to istniejący
import zweryfikowanej pełnej kopii z preimage; nie reset, nie wycinanie
indeksu w DevTools. Bez dobrej kopii konieczna jest osobna procedura naprawy
z pełnym audytem dowodu źródłowego, przed jakimkolwiek nadpisaniem.

Stare A–D readery nie rozumieją pola `runtime` i odmawiają (fail closed).
Root CAS blokuje starszego writera pozostawionego w otwartej karcie.
Rollback wymaga readera znającego oba kształty root lub jawnego odtworzenia
sprawdzonej kopii z zachowaniem preimage. Nie obniżać wersji DB i nie
przywracać samego starego JS do nowej reprezentacji.

## Pomiary i testy

Wyniki końcowe zostaną dopisane po pomiarach zamrożonego kodu i regresji.

## Odbiór na fizycznym Pixelu 9

1. Zachować pełną kopię dotychczasowej testowej bazy i szkiców. Zanotować
   wersję Chrome/Androida, release PWA, rozmiary/liczby sesji oraz źródło
   instalacji. Zamknąć pozostałe karty, zaktualizować kompletny release.
2. Oddzielić jednorazową instalację indeksu/konwersję od zwykłego startu.
   Nie zamykać w trakcie. Zweryfikować eksport i liczby danych po aktualizacji.
3. Wykonać osobno 10 zimnych i 10 ciepłych startów (także bez sieci),
   zmierzyć pierwszą reakcję i gotowość do treningu. Cel: gotowość <2 s.
4. Wykonać 20 zapisów/korekt oraz start/finish wszystkich jednostek.
   Mierzyć klik → natywny complete transakcji strict, osobno gotowy UI;
   raportować medianę/p95/max. Cele: zapis p95 <1 s, start sesji <1 s.
5. Sprawdzić szkic po zamknięciu procesu, drugi tab, quota/abort na izolowanej
   bazie testowej, Kalendarz, historię, rotację, notatki, statystyki, kopię i
   odtworzenie. Porównać dane z kopią sprzed aktualizacji.
6. Przy przekroczeniu celu zachować trace i liczby, bez czyszczenia bazy.
   Po etapie E zatrzymujemy dalsze optymalizacje syntetyczne; następny krok
   to ten odbiór urządzenia, chyba że pozostał istotny błąd.
