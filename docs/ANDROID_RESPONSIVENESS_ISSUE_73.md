# Issue #73 — diagnostyka responsywności i bezpieczna redukcja pracy

Punkt wyjścia: main `556655f1bcb6ddfccf35af6b125b380ae00b8036`, po scalonym PR #72.
Porównanie przed PR #72: `4230ca36b7b709de341d1421e275a8142169eb71`.
Plan nadrzędny i pełne Issue #73 przeczytano przed implementacją.

## Metoda

`scripts/measure_responsiveness.py` tworzy osobny artefakt z podanego commitu
(`git archive`, bez przełączania danych użytkownika) lub checkoutu. Serwuje tylko
allowlistę aplikacji na loopback. Każde powtórzenie ma nowy syntetyczny profil
przeglądarki. Nie otwiera profilu właściciela, nie usuwa jego baz i nie korzysta
z produkcyjnego Drive. Instrumentacja istnieje tylko w tymczasowym artefakcie;
jego SW otrzymuje poprawnie przeliczone hashe.

Chromium 154, Linux x86_64, Intel Xeon Platinum 8573C, 5 dostępnych CPU,
viewport 390×844, CDP CPU ×4. To nie jest emulacja sprzętu Android ani pomiar
fizycznego telefonu, wolnego flash, termiki czy ograniczeń pamięci telefonu.

Zarejestrowano pięć niezależnych powtórzeń każdego scenariusza. Mediana i p95
(nearest rank; przy n=5 p95 jest maksimum) nie opisują wiarygodnie ogona
rozkładu dla wszystkich urządzeń. Nie uruchamiano równocześnie regresji/testów
obciążających CPU. Syntetyczne scenariusze:

- legacy: 4 / 400 zakończonych sesji, 34 / 3400 wyników, różne ćwiczenia i serie;
- V2: 4 / 40 sesji z rzeczywistymi strukturami snapshotów, pozycji, serii,
  segmentów, L/P, back-offów i powiązań;
- w każdym profilu dodatkowe raw archiwum 4 MiB, zachowane w całości.

`cold` w danych oznacza **nowy dokument po zamknięciu strony przygotowującej
dane**, z wyczyszczonym cache HTTP; `warm` to kolejne otwarcie w tym samym
kontekście. To nie jest zimny proces Androida/OS. Przy `--offline` aplikacja
może już mieć precache SW z przygotowania profilu: cold nie dowodzi zimnej
sieci. `offline` to następne rzeczywiste otwarcie po `context.set_offline(True)`;
wszystkie dalsze akcje tego wariantu wykonują się offline. Osobna pełna
regresja testuje także instalację i upgrade PWA.

Czas akcji liczony jest od wysłania zdarzenia w stronie do oczekiwanego stanu
DOM i dwóch klatek rAF. Nie obejmuje narzutu Playwright auto-scroll/click, ale
obejmuje oczekiwanie kolejki aplikacji, commit i odmalowanie. `input` obejmuje
kg + reps i potwierdzenie szkicu w IndexedDB; synchroniczne capture mierzone
jest dodatkowo. Spany funkcji są **inkluzywne i mogą się nakładać**. Osobno
zapisano czas setterów innerHTML, transakcji/getAll, długie zadania i sumę
`max(0, task.duration - 50)` w oknie fazy (nie wynik Lighthouse/Web Vitals).

Odtworzenie (zależności jak dla testów Chromium):

```sh
python scripts/measure_responsiveness.py --ref 4230ca3 --runs 5 --offline --v2-counts 4 40 --output /tmp/pre72.json
python scripts/measure_responsiveness.py --ref 556655f --runs 5 --offline --v2-counts 4 40 --output /tmp/main.json
python scripts/measure_responsiveness.py --ref working --runs 5 --offline --v2-counts 4 40 --output /tmp/after.json
```

## Potwierdzone mechanizmy

1. `indexeddb.js/decode`: dla każdego wyniku `rows.sets.filter(...)` przeglądało
   wszystkie serie. Koszt O(wyniki × serie), powtarzany przy odczycie i kontroli
   zapisu. Profil CPU syntetycznych 400 sesji bez SW: callback tego filtra
   przetwarzania entries/series dominuje w odczycie i zapisie (CPU ×4).
2. `validateCatalog`: pełne kopie historii/snapshotów dla każdej wersji planu,
   mimo natychmiastowego zastąpienia sesji/wyników pustymi tablicami.
3. `load`: druga identyczna kopia `unverified=clone(result)` bez zmiany result
   pomiędzy kopiami; kopia odzyskiwania była już zachowana.
4. Natywne V2: pełna walidacja snapshotu przy każdej referencji serii, ponownie
   w projekcji i kontroli backupu. Profil CPU 4 sesji V2 + 4 MiB archiwum:
   `training-model/json` ~1912 ms z 6739 ms rozruchu oraz ~2169 ms z 7591 ms
   startu sesji. Dodano synchroniczne batch API: pełna walidacja snapshotu raz
   na batch i kompletna kontrola każdej referencji. Publiczne pojedyncze API
   pozostają pełnymi bramkami. Nie ma cache ważności pomiędzy operacjami.
   Analogiczny widok tylko do walidacji zastępuje zbędny clone w readerze v1/v2.

Optymalizacja nie usuwa walidacji: zachowane są wszystkie liczniki, relacje,
canonical roundtrip, digest, porównanie zapisanych rekordów, tokeny/CAS,
strict durability i oczekiwanie na `transaction.oncomplete`. Jednorazowa mapa
serii zachowuje sortowanie `position` i dokładne wartości, w tym brak/null.
Widok walidacyjny ma oddzielną mapę ćwiczeń, a walidatory są tylko odczytowe.
Pełna kopia odzyskiwania pozostaje dostępna przy odmowie weryfikacji.

## Zachowanie danych i zakres

Bez zmiany schematu/version IndexedDB, migracji, czyszczenia lub przycinania
historii/archiwów. Bez zmiany wyglądu Matrix i edytorów, rotacji, autosave,
tokenów, wznowienia szkiców, zapisu historii, formatów kopii i Drive.
Bez nowego etapu v6, przywracania v4/v6 lub Issue #61.

## Weryfikacja na fizycznym Androidzie

Nie wykonano. Po przeglądzie PR właściciel powinien porównać te same czynności
na tym samym profilu telefonu, z historią i szkicami zachowanymi:

1. Zanotować model telefonu, RAM, wersję Chrome/PWA i identyfikator wydania w Dane.
2. Zabezpieczyć pełną kopię poza przeglądarką. Nie czyścić danych ani cache DB.
3. Przez zdalne Chrome DevTools Performance nagrać otwarcie, start treningu,
   rozwinięcie ćwiczenia, otwarcie wyniku, wpis kg/reps, zapis i nawigację.
4. Powtórzyć po ponownym otwarciu i offline, co najmniej pięć razy. Oddzielić
   cold process od samego reloadu, instalacji/aktualizacji SW i czasu sieci.
5. Sprawdzić niedokończony wpis `1,`, wznowienie po zamknięciu oraz drugą kartę.
   Nie uruchamiać w tym czasie eksportu ani ręcznego kolektora szkiców.

Zapisać liczby/anonimowe agregaty (czasy i long tasks), bez publikowania plików
backupów, raw rekordów, tokenów czy prywatnego profilu przeglądarki.
Ostateczna poprawa zgłoszonego telefonu wymaga tych pomiarów. Pozostające
koszty pełnego zapisu/weryfikacji rosną wraz z danymi; ten PR nie obiecuje
stałego czasu dla dowolnej historii ani stałego RAM.
