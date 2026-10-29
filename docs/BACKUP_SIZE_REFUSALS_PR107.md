# PR #107 — przyczyny odmowy i niepełny raport diagnostyczny

Baza: `main` `d79a297` po PR #106. Przeczytano plan nadrzędny, AGENTS.md oraz opis diagnostyki PR 1. Zakres: wyłącznie wyjaśnienie odmów istniejącego pomiaru i osobny, anonimowy raport niepełny. Nie zmieniono eksportu, formatów kopii, importu, Drive, IndexedDB v2 ani writerów historii.

## Ograniczenia i pochodzenie wartości

| Rodzaj | Próg produkcyjny (bez zmian) | Wartość w komunikacie |
| --- | ---: | --- |
| Pojedynczy obiekt | 67 108 864 B / 64 MiB | Maksimum zadeklarowane w metadanych root lub rozmiar zadeklarowany w odczytanym rekordzie. Bez pobierania zbyt dużego obiektu tylko w celu ustalenia przyczyny. |
| Checkpointy łącznie | 67 108 864 B / 64 MiB | Budżet z metadanych pomniejszony o rozmiary wszystkich odczytanych obiektów; przed odczytem checkpointów. Ewentualnie policzony rozmiar pojedynczego checkpointu. |
| Rekordy | 250 000 | Liczba z metadanych lub dolna granica ustalona podczas enumeracji kluczy, jawnie „co najmniej”. |
| Analiza semantyczna jednego katalogu/modelu/pakietu | 8 388 608 B / 8 MiB | Profil bajtowy wcześniej odczytanego obiektu, przed `JSON.parse`. Nie ujawnia jego ID ani nazwy planu. |
| Czas | 120 000 ms | Monotoniczny czas od rozpoczęcia pomiaru lub klienta do wywołania istniejącego watchdoga. |

Komunikat zawiera nazwę ograniczenia, ustaloną wartość, jej pochodzenie i próg. Bajty podawane są dokładnie, obok zaokrąglonej wartości MiB. Przy niedostępnej wartości nie wpisujemy zera ani estymaty. Nie klasyfikujemy nieznanej awarii workera/silnika lub braku dostępu jako konkretnego przekroczenia pamięci.

## Dwa odrębne wyniki

Pełny pomiar i jego dotychczasowy plik pozostają bez zmian. Odmowa nadal odrzuca Promise pomiaru, zamiast zwracać częściowe dane jako sukces.

Przy rozpoznanej odmowie worker może dołączyć **osobny NIEPEŁNY raport diagnostyczny**. Przed udostępnieniem ponownie odczytuje mały root i porównuje go z początkowym; UI dodatkowo sprawdza rewizję i stan błędu. Zmiana rewizji/root, błąd potwierdzenia lub anulowanie wykluczają udostępnienie tych liczników.

Raport niepełny ma `format: pushpull-backup-size-incomplete` i `complete: false`. Jego ścisła allowlista obejmuje:

- przyczynę: `kind`, `value` lub jawne `null`, `limit`, `basis` (wyłącznie stałe enumy i liczby);
- `metadata`: zadeklarowane sesje, wyniki, snapshoty, archiwa, liczba rekordów protokołu, budżet obiektów/checkpointów i największy obiekt;
- `progress`: dolna granica liczby odczytanych kluczy i liczba w pełni policzonych obiektów;
- względny czas `elapsed` w ms.

Liczniki metadanych są opisane jako **zadeklarowane przez bazę**, nie jako niezależnie przeliczona lub zwalidowana zawartość. Weryfikujemy ich poprawność liczbową i stabilność root. Raport nie jest audytem integralności bazy. Nie zawiera liczby nieodczytanych planów, nazw, notatek, wyników treningowych, dat, ID, rewizji/root/hash, tokenów ani raw. Nie zawiera `sourceBytes`, `storedBytes` ani sumy rozmiaru kopii. Budżety/progres nie są sumowane jako pełna kopia.

UI pokazuje osobny blok „Raport diagnostyczny NIEPEŁNY” i osobny przycisk/pliki `pushpull-rozmiar-raport-niepelny.json`. Schemat jest sprawdzany także po stronie klienta. Raport ma <8 KiB. Nieznane pola, prywatne teksty lub błędne oznaczenie kompletności są odrzucane.

Gdy klient musi zakończyć nieodpowiadający worker po 120 s, może nie mieć żadnych potwierdzonych liczników bazy. Wówczas podaje ograniczenie czasu i znany czas operacji, ale nie tworzy raportu niepełnego z domysłów. Weryfikacja małego root po odmowie nie restartuje budżetu ani nie uruchamia kolejnych odczytów dużych rekordów; watchdog pozostaje bez zmian.

Anulowanie kończy worker i usuwa oba rodzaje raportów. Tożsamość operacji blokuje spóźnioną odmowę, także po ukończeniu nowego pomiaru. Nieaktualne dane nie mają przycisku pobierania. Zmieniana jest tylko sekcja diagnostyki; nawigacja i inne formularze pozostają dostępne.

## Rzeczywista weryfikacja lokalna

- Node: **260/260 PASS**. Dedykowany moduł: **9/9 PASS**. Odtworzenie wszystkich pięciu odmów, sprawdzenie wartości względem niezależnych fixture’ów, pochodzenia wartości, dolnej granicy kluczy, limitów, ścisłej allowlisty, braku pełnych sum i nieznanych liczników. Zmiana rewizji lub anulowanie w trakcie końcowego potwierdzenia usuwa niepełne dane.
- Chromium/PWA: **25/25 PASS**. Obejmuje 8 scenariuszy diagnostyki, pozostałe działania Dane, B1/B2 Drive, build i aktualizacje z historycznych wydań. Nowe przypadki sprawdzają komunikaty/pliki dla czterech limitów danych, rzeczywisty klientowy watchdog bez liczników, spóźnioną odmowę po anulowaniu, raport niepełny offline i unieważnienie po nowym zapisie. Sprawdzenie 360/390/412 px oraz wszystkich rekordów IndexedDB i localStorage przed/po.
- Małe progi są stosowane **wyłącznie w serwowanych fixture’ach testowych**, aby odtworzyć każdy mechanizm bez alokowania setek MB. Osobny test offline używa rzeczywistych domyślnych progów i izolowanej, podpisanej fixture metadanych deklarującej maksimum 64 MiB + 1 B. Nie twierdzi, że utworzono rzeczywisty tak duży obiekt. Obie metody weryfikują pochodzenie wartości „według metadanych”.
- Zachowano wcześniejszy test dużego archiwum (wirtualne kodowanie >200 MB), 400 snapshotów, małego heapu Node, błędów i pełnego pomiaru. Na ich podstawie nie deklarujemy nowego benchmarku ani wyniku telefonu.
- Składnia, zgodność hashy/SW, build i `git diff --check`: PASS. Release `3b6f0e3d9801bf7638cf7441`.
- Wynik istniejącego pełnego CI dla końcowego commitu jest podany w PR. Workflow i runner pozostają bez zmian; bez ręcznego dublowania przebiegów.

## Ograniczenia i odbiór

Nie mamy dostępu do fizycznego Pixela 9 ani jego rzeczywistej bazy. Nie określamy z góry, który próg spowodował tam odmowę. Po zatwierdzonej aktualizacji użytkownik może uruchomić diagnostykę i przekazać mały raport NIEPEŁNY, bez wysyłania kopii >200 MB. Pierwsza wykryta odmowa nie oznacza, że nie istnieją inne ograniczenia; nie podnosimy progu, aby je odkryć.

Nie zmniejszono wielkości backupów, nie usuwano danych, nie naprawiano zagnieżdżonych archiwów ani nie zmieniano semantyki odzyskiwania. Brak scalenia i ręcznego wdrożenia; odbiór fizycznego urządzenia pozostaje osobny.
