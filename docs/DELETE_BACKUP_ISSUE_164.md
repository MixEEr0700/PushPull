> Aktualizacja: po zatwierdzeniu kierunku wdrożenie opisuje [REFERENCE_PREIMAGE_ISSUE_164_IMPLEMENTATION.md](REFERENCE_PREIMAGE_ISSUE_164_IMPLEMENTATION.md). Poniżej zachowano wcześniejsze pomiary i projekt; ich określenie „PR diagnostyczny” dotyczy poprzedniego etapu.

# #164 — źródło odmowy i minimalna zmiana do zatwierdzenia

Stan źródła: main 0bffe78, wyłącznie dane syntetyczne. PR diagnostyczny: **nie naprawia jeszcze produkcyjnego usuwania**. Użytkownik wymaga przedstawienia dowodów i projektu przed zmianą architektury kopii; na tej granicy implementacja została zatrzymana. Nie zmieniono aplikacji, limitów, PPC1, archiwów ani migracji.

## Potwierdzona przyczyna i granice wnioskowania

`backupBefore` w journal-database.mjs generuje cały v3 z source-backed modelem, po czym `JSON.stringify` umieszcza go w nowym `before-import.raw`. Wcześniejsze archiwa są częścią tego źródła. `createProtocol` traktuje każdy rekord archiwum jako jeden obiekt i jeszcze raz koduje JSON. Sam poprawny ciąg raw może mieścić się w limicie, a otaczający JSON już go przekraczać. Rosną także projekcje sesji i wyników oraz pełne snapshoty; archiwa nie są jedynym kosztem.

Produkcja ma objectBytes=134217728 (128 MiB), totalBytes=536870912 (512 MiB). `encodedJSON` w journal-index.mjs rzuca dokładnie `Backup: protocol JSON size` przy limicie obiektu w objectRecord oraz przy pozostałym budżecie checkpointów w checkpointDigest. Ogólny limit zachowanych obiektów/nodów ma osobny komunikat `protocol retained size/count limit`. Dlatego sam komunikat z Pixela **nie pozwala ustalić**, czy odmówił rekord archiwum czy checkpoint; nie odczytano prywatnej bazy.

Bezpośredni test rzeczywistego limitu: ASCII payload 134217728 B po zakodowaniu jako JSON ma 134217730 B i objectRecord odmawia z dokładnym komunikatem. Test nie zwiększa limitu.

## Aktualne pomiary

Skrypt scripts/diagnose_delete_164.mjs używa rzeczywistych createLegacyModelFromSource, createProtocol i objectRecord. Profile wzrostu mają testowo OBNIŻONE limity 8 MiB/32 MiB; to skala kontrolowana, nie twierdzenie o przekroczeniu produkcyjnego limitu przez te małe profile. Wykonano osobny test prawdziwej granicy 128 MiB. Dane liczbowe i czasy: DELETE_BACKUP_ISSUE_164_MEASUREMENTS.json. Nie są to pomiary Androida.

| Profil | Operacja | Sesje | Data B | Stare archiwa B | Nowy preimage B | Nowy rekord archiwum JSON B | Wynik przy 8 MiB/obiekt |
|---|---:|---:|---:|---:|---:|---:|---|
| mały | 0 | 5 | 6931 | 2 | 29966 | 37524 | PASS |
| mały | 3 | 5 | 6931 | 621473 | 1114887 | 2049345 | PASS |
| historia | 0 | 11 | 601316 | 2 | 1339420 | 1549780 | PASS |
| historia | 2 | 11 | 601316 | 5911005 | 9773747 | 15030755 | protocol JSON size |
| historia + raw | 0 | 11 | 601316 | 524383 | 2388105 | 3647073 | PASS |
| historia + raw | 1 | 11 | 601316 | 4171457 | 8552949 | 14847457 | protocol JSON size |
| większa historia | 0 | 40 | 1011666 | 2 | 2341052 | 2735330 | PASS |

Profil 40 sesji: 133 wyniki, 35 snapshotów. Snapshoty zajmują 725172 B **wewnątrz Data**, nie należy dodawać ich drugi raz. Katalog 10647 B. Porównanie raw/preimage/rekordu pokazuje narzut projekcji i kolejnego escapowania; sourceBytes to całe źródło po dodaniu archiwum, również nie należy sumować go z częściami.

W seriach wzrostu bieżące data/catalog pozostają stałe i nie kasuje się sesji — izoluje to koszt samej ochrony `backupBefore`, a nie symuluje ukończonego usunięcia. Minimalny profil nie ma modelu V2; profil historyczny używa rzeczywistych struktur V2 i importowanego planu. Nie dowodzi to rozmiaru konkretnej bazy Pixela.

`replaceSource` zachowuje wszystkie stare journalObjects i journalIndex oraz journalCheckpoints. Budżet retained obejmuje więc także obiekty już nieobecne w bieżącym source. Checkpointy są osobną składową allocation, nie katalogiem archiwów raw. Test granicy checkpointów wykazał ten sam komunikat przy obniżonym budżecie, przed zapisem źródła.

## Atomowość odmowy

Test Chromium na izolowanej bazie: stary model + archiwum z dużą liczbą cudzysłowów/backslashy; podczas testu tylko obiektowy limit modułu jest obniżony do 1 MiB. Dodanie archiwum przechodzi, próba usunięcia z backupBefore odmawia. Dokładne porównanie wszystkich rekordów IndexedDB przed/po, stan aplikacji i restart: PASS. Nie ustalono w ten sposób stanu rzeczywistego telefonu.

## Wariant rekomendowany — referencyjny preimage, do zatwierdzenia

Nowe kopie sprzed usunięcia opisać manifestem stanu protokołu, zawierającym poprzedni root/revision/epoch, nagłówki uporządkowanych rekordów i SHA-256 referencji do zachowanych obiektów, indeksów i checkpointów. **Nie** wkładać treści poprzednich raw i checkpointów do kolejnego stringa. Wykorzystać obecne content-addressed obiekty, które już są zachowywane przez replaceSource. Zmienia to kontrakt nowego punktu ratunkowego i jego odczytu, dlatego wymaga zatwierdzenia.

1. Zbudować manifest z uwierzytelnionego, stabilnego odczytu przed zmianą, sprawdzić kompletność referencji oraz limity.
2. Rekonstruować z manifestu wcześniejsze źródło i niezależnie porównać je z pełnym źródłem sprzed operacji przed dopuszczeniem kasowania. Same SHA nagłówków nie zastąpią testu rekonstrukcji.
3. Zapisać referencyjny punkt i zmianę sesji w tej samej transakcji CAS/readback/strict complete. Awaria manifestu, quota, przerwanie lub konflikt — brak usunięcia.
4. Zachować wszystkie stare archiwa i checkpointy bez migracji i bez retencji. Nowe punkty odwołują się do poprzednich obiektów zamiast je ponownie kodować.
5. Dodać odczyt/podgląd i odzyskiwanie tego rodzaju punktu w istniejącym mechanizmie kopii ratunkowych. Przy eksporcie rozwiązać referencje do kompletnego odtwarzalnego pliku; **nie** eksportować samych lokalnych wskaźników jako przenośnej kopii.

PPC1 kanoniczne nie obejmuje wszystkich technicznych archiwów: sama kopia PPC1 bez pełnej ewidencji ratunkowej nie jest równoważna obecnemu backupBefore. Istniejący saveRescue może pomóc w izolacji, lecz sam w sobie nie rozwiązuje rosnącej pełnej ewidencji przy każdym usunięciu. Nie zastąpiono nim ochrony bez dowodu równoważności.

Zmiana nie usunie istniejącego bloatu i nie sprawi, że dowolnie wielki dziennik zmieści się w limicie 512 MiB. Jeśli zachowane obiekty już przekraczają budżet, operacja musi odmówić i zachować stan. Osobne zatwierdzenie byłoby potrzebne do retencji lub przebudowy takiej bazy. Nie proponujemy podnoszenia limitów ani usuwania danych.

## Testy i pozostały zakres po akceptacji projektu

Wykonano: 2 Node (escaping/limity i checkpointy) PASS; 1 Chromium (rzeczywista odmowa usunięcia i identyczne rekordy/restart) PASS; pomiary skryptu oraz realnej granicy 128 MiB. Pełny CI jest w checks PR.

Po akceptacji projektu trzeba zaimplementować oraz sprawdzić udane usunięcie dużej sesji, drugie usunięcie bez rekurencji, pełne przywrócenie wszystkich danych sprzed operacji, brakujące/uszkodzone referencje, quota/abort, konflikt rewizji i restart. Te funkcje **nie są jeszcze naprawione ani zaliczone** przez obecny PR diagnostyczny.

Pixel 9: do czasu działającej i zweryfikowanej poprawki pozostawić błędną sesję. Przed późniejszym odbiorem pobrać niezależną PPC1 i sprawdzić odtwarzanie w izolowanym profilu; nie usuwać ręcznie magazynów/archiwów. Odebrać jedną operację dopiero po zatwierdzonym wdrożeniu, potem sprawdzić pozostałe sesje i punkt ratunkowy. Obecne testy nie wykonują niczego na telefonie.
