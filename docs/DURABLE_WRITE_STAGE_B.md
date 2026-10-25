# Issue #75 — etap B: jedna przygotowana rewizja

Status: implementacja etapu B, osobna gałąź `perf-stage-b-prepared-model`.
Punkt odniesienia: #79 `4a74d1d`, na main `2504e5a` po #76/#78.
Etap B został zatwierdzony przez właściciela. Testowy charakter historii/planu
nie blokuje zmian architektury; nie usuwa się automatycznie żadnych danych.

## Implementacja

- `createLegacyModelFromSource` przyjmuje strukturę, weryfikuje JSON i pełny
  kontrakt legacy v2, odłącza mutowalny graf przed await i serializuje źródło
  raz. Nie parsuje własnego JSON po serializacji. Reader tekstowy nadal
  sprawdza duplicate keys, liczby bezstratne i pełny kontrakt niezaufanej kopii.
- Walidacje JSON/modelu/snapshotu mają prywatne dowody w WeakSet, nadawane
  dopiero po udanej kontroli wszystkich deskryptorów, potomków i relacji.
  Płytki freeze, ID, revision lub wywołanie eksportowanej funkcji nie daje
  dowodu. Nieznane pola również należą do grafu. Mutowalne wejścia zawsze
  przechodzą pełną walidację ponownie.
- W builderze zachowuje się zweryfikowane niezmienne snapshoty zamiast ponownie
  je klonować. `createBackup` może współdzielić wyłącznie kompletny niezmienny
  payload. Mutowalne wejście/metadata są odłączane. Format v3, raw, canonical,
  SHA i liczniki pozostają zgodne z writerem/readerem #79.
- Deskryptor legacy raw może powstać tylko z widoku wystawionego przez pełną
  granicę walidacji. WeakMap przechowuje wersję, nie drugi parsed source.
  Skopiowany/fałszywy deskryptor przechodzi normalny reader, nie otrzymuje
  dowodu przez podobne pola czy raw. Nie ma globalnego cache wielkich stringów.
- Zapis normalny sprawdza raz, przed transakcją, że dekoder przygotowanych
  wierszy odtwarza cały zwalidowany kandydat. Oczekiwane wiersze/root są
  zamrożone. W transakcji odczytuje się wszystkie zapisane wiersze/root i
  porównuje pełne wartości z przygotowaną reprezentacją, w tym nieznane pola,
  pozycje i snapshoty. Zgodność z kompletną zwalidowaną reprezentacją jest
  dowodem jej walidacji; nie odtwarza się i nie waliduje jej drugi raz.
- CAS nadal odczytuje i porównuje pełny poprzedni model oraz rewizję w tej
  samej transakcji. Nowy model nadal ma pełny readback. Pominięto wyłącznie
  dodatkowy nieużywany odczyt starego modelu podczas kontroli źródłowych tabel.
- Dopiero strict complete publikuje nowy stan. Import/restore i inicjalizacja
  zachowują pełną dotychczasową ścieżkę weryfikacji i dodatkowy readback importu.
  Katalog i importowane archiwa są odłączane w momencie wywołania commit,
  więc zmiana opcji przez wywołującego podczas await nie zmienia kandydata.

Nie zmieniono UI/Matrix, pending z #78, rotacji, szkiców, planów, historii,
formatów backupów v1–v6, mechanizmu Drive, schematu IndexedDB ani produkcyjnego
przywracania. Nie wdrożono nowego writera przyrostowego.

## Weryfikacja integralności

Nowe testy Node porównują **dokładny JSON, raw i digest** z poprzednim writerem
#79, odczytują nowy dokument starym readerem i obejmują natywne V2, niezależne
strony/segmenty/grupy, nieznane pola, Unicode, lone surrogate i duży raw.
Testują mutację po await, płytki freeze, nieudane walidacje, fałszywe dowody,
nieprzenoszalne wartości i nadal odrzucane duplicate keys/lossy decimals.
W procesie z heap 128 MiB 12 kolejnych rewizji z różnym raw 3 MiB nie może
utrzymywać zwolnionych historii przez cache dowodów. To test Node, nie pomiar
szczytowej pamięci Androida.

Nowe testy Chromium podmieniają snapshot w root i nieznane pole wiersza przy
niezmienionych licznikach/SHA. W obu przypadkach transakcja jest wycofana,
szkic/archiwa pozostają i nie ma sukcesu. Osobny test potwierdza izolację
katalogu, archiwum i nieznanych pól od zmian wywołującego podczas await.
Asercje istniejących testów nie zostały osłabione; zmieniono tylko opis testu
batch references, aby odpowiadał dopuszczonym dowodom niezmiennych grafów.

## Pomiary i ograniczenia

`scripts/measure_stage_b.py` wykonuje sparowane porównania #79/etap B,
naprzemiennie przed/po i po/przed, po 3 niezależne procesy/profile i 8 zapisów na profil.
Finalna seria natywna: pusta/4 sesje V2 bez dodatkowego raw oraz 4/40 sesji
z raw 4 MiB. Wcześniejsza osobna seria callbacku obejmuje też raw 16 MiB
Unicode/escapes; nie mieszamy tych granic czasowych. Wszystko offline,
390×844, CPU ×4 w Chromium/Linux. To nie emulator ani pomiar fizycznego Pixela.
Zegar i programowe kliknięcie są teraz w tej samej ewaluacji, bez wcześniejszej
rundy Playwright między początkiem zegara a zdarzeniem. Kończy się na strict
history transaction oncomplete **przed resolve Promise**, nie późniejszym
listenerze ani zapisie szkicu. Niezależnie zapisuje event.timeStamp oraz
późniejszy callback. Mediana standardowa i p95
nearest-rank; 8 zapisów/profil jest skorelowanych, liczba niezależnych profili
mała, współdzielony host wnosi wariancję.

Zachowanie starych sesji/wyników/snapshotów i wszystkich archiwów potwierdzane
jest SHA przed/po każdym profilem. Start aplikacji/start treningu i trwały
szkic są poza czasem zapisu. Nie przeniesiono pracy do nowego startup cache.
Nieznane są dokładne wolumeny bazy oraz wersje Chrome/Androida właściciela;
wiadomo: Pixel 9, zgłoszone około 10 s, drugi telefon z czystą bazą szybki.

Finalne próbki natywne: `performance/stage-b-measurements.json`; tabele i wyniki
pełnej regresji są uzupełniane po zakończeniu przebiegów.

Kontrola zegara wykazała błąd wcześniejszego harnessu: listener complete
podłączony przy put mógł uruchomić się po kontynuacji Promise i publikacji
pamięci. W realnym Chromium potwierdzono kolejność: pierwszy listener,
oncomplete, await-resumed, późny listener. Dlatego wcześniejsze 288 próbek
zachowano osobno jako czasy późniejszego callbacku; nie są używane jako
natywny strict complete. Finalną serię zmierzono ponownie z markiem w
oncomplete przed resolve. Nowy test wymusza 60 ms pracy po complete i
potwierdza, że ta praca nie zawyża natywnego zegara. To korekta narzędzia,
nie kolejna optymalizacja kodu aplikacji ani zmiana asercji integralności.

## Finalny wynik natywnego zapisu

192 próbki: 4 scenariusze × 2 wersje × 3 profile × 8 wyników.
Przed = #79 `4a74d1d`; po = etap B, te same assety runtime co `977faea`.
Czas w ms, mediana / p95 / max:

| Profil V2 | Przed | Po |
|---|---:|---:|
| Pusta historia, bez dodatkowego raw | 353,9 / 414,4 / 419,8 | 266,6 / 295,5 / 299,6 |
| 4 sesje, bez dodatkowego raw | 1093,7 / 1191,9 / 1271,1 | 635,5 / 681,8 / 699,3 |
| 4 sesje, raw 4 MiB | 1545,2 / 1849,1 / 2677,1 | 932,9 / 1027,5 / 1295,6 |
| 40 sesji, raw 4 MiB | 8675,5 / 9120,1 / 9149,3 | 4766,4 / 5274,3 / 5344,2 |

**Cel <=1 s dla dużej historii nie został osiągnięty.** Mediana dla 40 sesji
spadła o 45,1%, ale nadal wynosi 4,77 s. Wariant 4 sesji z raw ma p95 ponad
1 s. Wynik pustej/małej bazy w chmurze nie potwierdza SLA fizycznego Androida.
Nie zamykamy Issue #75 na podstawie tych wyników.

W V2 40 średnie rozłączne etapy: budowa modelu 5344 → 2081 ms,
przygotowanie odwracalnej projekcji 0 → 325 ms, kontrola źródła 944 → 112 ms,
odczyt źródła 269 → 135 ms. Kodowanie/hash całego źródła pozostaje około
453 ms, pełny zapis tabel 233 ms, model write/readback 532 ms, finalny root
+ strict complete 142 ms. Są to przedziały etapów, nie sam czas CPU albo fsync.
Pełne porównanie modelu, duże root.rest i duży model nadal wymagają pracy
zależnej od całej historii i archiwów.

[Tabele etapów oraz UI/callback/native](performance/stage-b-tables.md) i
[wszystkie finalne próbki, rozmiary i hashe](performance/stage-b-measurements.json).
Siedem zmienionych assetów runtime potwierdzono hashami; app.js, CSS i manifest
są identyczne z #79. Każdy profil potwierdził zachowanie historii i archiwów.

Odtworzenie serialne:

```sh
python scripts/measure_stage_b.py --before 4a74d1d --after working --cases v2-empty v2-small v2-small-archive4 v2-large-archive4 --raw-directory /tmp/stage-b-native-fresh --output /tmp/stage-b-native.json
```

## Wyniki testów i publikacja

- Pełny Node: **192/192 PASS**, 0 skipped, 11,078 s.
- Nowe ukierunkowane testy Node: **7/7 PASS**, w tym oracle poprzedniego
  writera/reader i kontrola retencji pod 128 MiB.
- Ukierunkowane Chromium: migracja/model CAS/readback **8/8 PASS**,
  przygotowany zapis **3/3 PASS**, natywny zegar **1/1 PASS**.
- Pełna regresja Chromium/PWA: **140/140 PASS**, 634,922 s; wszystkie
  przypadki wykonane, bez pomijania. Obejmuje IndexedDB/CAS, quota/abort,
  restart/crash, szkice, wiele kart, podwójne kliknięcia, historię/plany,
  backupy i odtwarzanie, instalację/offline/aktualizacje PWA.
- `build_release.py --check`: PASS; produkcyjny build `dist/stage-b-final`:
  PASS, release `9fa85bdb76b987281bef5932`, bez deploymentu.
- `git diff --check`: PASS. GitHub Actions **nie uruchomiono/nie zweryfikowano**
  w tej sesji z powodu blokady API opisanej poniżej; lokalne PASS nie zastępuje CI.

API GitHuba w działającym środowisku jest blokowane polityką sieci (Forbidden,
`api.github.com` poza allowlistą); Git fetch/push działa. Zapisano odrębny
projekt dodania wyłącznie tej domeny, wymagający zapisania/publikacji w UI
środowiska. Nie zmieniano workflow, poświadczeń ani ustawień płatnych usług.
GitHub Actions nie należy uznawać za wykonane bez rzeczywistego wyniku.

Jeśli duża historia pozostaje wyraźnie ponad 1 s, następny krok to
[odrębny projekt zapisu przyrostowego](INCREMENTAL_WRITE_P0_DESIGN.md),
z nowym jawnym protokołem, CAS i bezpieczną aktualizacją. Nie wdrożono go
w ramach etapu B i nie kontynuuje się kolejnych marginalnych optymalizacji.
