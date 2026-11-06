# #164 — zatwierdzone referencyjne punkty sprzed zmiany

## Wdrożone

`backupBefore` zapisuje checkpoint protokołu: poprzedni stan/root/revision/epoch, uporządkowane nagłówki rekordów i inwentarz zachowanych obiektów, węzłów oraz checkpointów. Manifest ma SHA-256, własny limit wielkości i przechodzi pełną rekonstrukcję źródła przed dopuszczeniem zapisu. Równość źródła jest sprawdzana bez budowania kolejnych pełnych stringów JSON. Archiwa raw nie są ponownie wkładane do nowego preimage.

Checkpoint i zmiana dziennika powstają w jednej istniejącej transakcji z CAS, readback i strict complete. Awaria limitu/manifestu/zapisu lub zmiana rewizji blokuje zmianę. Oryginalne archiwa, checkpointy i niezmienne obiekty pozostają zachowane. Nie ma migracji, retencji ani podnoszenia limitów.

Nowe punkty są osobnymi checkpointami, NIE archiwami z lokalnymi wskaźnikami w `source.archives`. `backups()` i `backupLabel()` wyliczają je z uwierzytelnionych referencji stanu. `readBackup()` rekonstruuje wcześniejszy stan i tworzy przenośny PPC1 zawierający komplet potrzebnych rekordów protokołu. W istniejącym wyborze kopii ratunkowej dostępne są podgląd oraz pobranie `.ppc1`. Stare archiwa nadal zwracają dotychczasowy raw i pozostają czytelne.

Nowy plik punktu ratunkowego używa istniejącego kontenera PPC1 i transportu JSON, z jawnym payloadem `pushpull-protocol-rescue` v1. Reader sprawdza cały protokół, checkpointy v1 tym samym walidatorem co aplikacja, wszystkie SHA oraz rekonstrukcję wcześniejszych punktów. Niekompletne/nieznane sekcje są odrzucane. Nie jest to zmiana zwykłej kanonicznej kopii PPC1 ani jej zakresu danych.

Przy zatwierdzonym imporcie takiego pliku istniejący importer instaluje też zweryfikowane zależności referencji w tej samej transakcji. Kolizje niezmiennych ID z różną zawartością blokują import. Stan aktualnej bazy ma własny nowy punkt sprzed przywrócenia. Starsze punkty z importu pozostają ponownie odczytywalne i przenośnie eksportowalne po restarcie. Przywracane są dokładne dane wybranego źródła; rewizja robocza jest nowa, a dotychczasowe archiwa celu pozostają zachowane zgodnie z dotychczasowym mechanizmem importu.

## Granice zakresu

Punkt odtwarza pełne źródło protokołu (data/catalog/archives), checkpointy i wymagane niezmienne obiekty, zgodnie z dotychczasowym zakresem backupBefore. Nie zastępuje lokalnych szkiców, buforów ani konfiguracji Google w meta/localStorage; usuwanie sesji ich nie kasuje. To nie nowa migracja wszystkich magazynów.

Zwykłe eksporty JSON/PPC1 pozostają w dotychczasowych formatach i zakresach. Tak jak wcześniej nie są eksportem całego technicznego zbioru checkpointów. Kompletny przenośny eksport konkretnego nowego punktu wykonuje się przez jego pobranie w kopiach ratunkowych. Stara aplikacja bez tego readera nie obsłuży nowego pliku ratunkowego; musi odmówić, zamiast pomijać dane.

## Weryfikacja syntetyczna

- Node: pełna rekonstrukcja source i zachowanie opaque raw; uszkodzone SHA/manifesty oraz brakujące referencje odrzucane.
- Node: dotychczasowe granice escaping/obiektu i checkpointów nie są podnoszone.
- Chromium: 40 sesji z archiwum o dużym narzucie escapowania. Testowy limit obiektu OBNIŻONY do 1 MiB; oba usunięcia przechodzą, pozostałe rekordy treningów są zachowane. Plik drugiego punktu → czysty profil → świadomy import → restart → dokładnie odtworzone dane z chwili sprzed drugiego usunięcia. Wcześniejszy punkt ponownie daje się odczytać/wyeksportować w tej nowej bazie.
- Chromium: limit manifestu (testowo obniżony tylko dla modułu referencji) i przerwanie transakcji zachowują wszystkie rekordy IndexedDB identycznie; restart działa.
- Chromium: obca rewizja blokuje zapis bez dodatkowego checkpointu.
- Dotychczasowe testy usuwania sesji i planów nadal przechodzą; odczyt ich nowej kopii sprawdza teraz payload PPC1 zamiast oczekiwać starego zagnieżdżonego v3 JSON.

Bieżący wynik pełnego CI jest w checks PR. To testy syntetyczne desktopowego Chromium/Node, nie pomiary Pixela 9 ani prywatnych danych.

## Już nadmiernie rozrośnięta baza

Zmiana nie zmniejsza żadnego starego raw, checkpointu ani puli niezmiennych obiektów. Nadal obowiązuje limit obiektu 128 MiB i łączny limit 512 MiB protokołu oraz odrębne limity PPC1, parsera i dekompresji. Manifest/inwentarz także rośnie z liczbą rekordów i punktów; nie jest nielimitowany. Ich późniejsze porządkowanie wymaga odrębnej, zatwierdzonej polityki.

Jeśli stara baza nie przechodzi pełnej weryfikacji, ma pojedynczy obiekt ponad limitem, za duży checkpoint albo brak pojemności/quota na nowy bezpieczny punkt, usuwanie MUSI nadal odmówić. Również eksport przenośnego punktu może odmówić przy istniejących limitach rozmiaru/czasu/pamięci. Nie obiecujemy naprawy takich baz przez tę zmianę i nie obcinamy ochrony dla wymuszenia sukcesu.

Odbiór Pixel 9 dopiero po zatwierdzonym wdrożeniu: najpierw niezależna kopia i potwierdzony odczyt; jedna świadomie wybrana błędna sesja, kontrola pozostałych wyników i nowego punktu, pobranie punktu i próba odtworzenia w izolowanym profilu. Brak zgody na ręczne kasowanie magazynów/archiwów i brak wykonania na telefonie w tej pracy.
