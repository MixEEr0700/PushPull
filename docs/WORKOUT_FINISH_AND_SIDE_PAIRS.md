# Matrix: notatki, pary L/P, wyniki i kończenie ze szkicami

Baza: `main` po PR #97, `de84e6361ad18baeb17a1b51c7fae88b92fd7390`. Jedna gałąź i jeden PR. Bez Issue #94, migracji/resetu bazy, zmiany formatów kopii lub Drive.

Przy wznowieniu istniała rozpoczęta implementacja w czterech plikach, bez commitu. Zachowano ją, poprawiono wykryte błędy i dokończono testy; nie odtwarzano projektu od nowa.

## Notatki

Usunięto widoczny nagłówek Notatki i drugi piktogram przy pustej treści: pozostaje dyskretny plus. Własna treść ma tekst i ołówek. Zachowano nagłówkowy notatnik, zwijanie, dostępne etykiety, auto-wysokość, `userNotes` i ochronę źródeł z PR #97. Nie przenosimy tekstów trenera do własnej notatki. Dotychczasowa blokada kontekstu niewersjonowanego/niejednoznacznego pozostaje.

## Serie i strony

- Przy wierszach edytora nie ma napisu back-off. Role, cele, ID, liczba i wartości serii pozostają w modelu. Parametry planu i historia nadal rozróżniają back-off/drop.
- W trybie L/P są sekcje **Seria 1 (L/P)** itd. Lewa i prawa są domyślnie niezależne. Pierwszy szybki wpis do nietkniętego formularza nie wymaga potwierdzenia; rzeczywiste indywidualne zmiany nadal są chronione. Dodanie tworzy całą parę z pustymi wartościami; usunięcie po potwierdzeniu usuwa obie strony ze szkicu, także pierwszą i ostatnią parę. Pusty szkic da się wznowić, ale nie zapisać jako wynik.
- **Scal L/P** łączy sterowanie formularzem, zachowując dwa rzeczywiste rekordy stron i ich ID. Nie zmniejsza liczby zapisanych stron ani tonażu. Równe wartości można połączyć bez wyboru; przy asymetrii trzeba wybrać L lub P i osobno potwierdzić zastąpienie wartości. Rozdziel L/P ponownie udostępnia niezależne pola. Stan szkicu przeżywa restart.
- Różna struktura segmentów lub metadane blokują scalanie do ręcznego uporządkowania. Kopiowanie L/P zachowuje dodatkowe segmenty docelowe; nie skraca drugiej strony po cichu. Segmenty można usuwać istniejącymi jawnymi kontrolkami.
- Stare niekompletne/niejednoznaczne układy nie otrzymują dopisanych wartości ani usuniętych wierszy. Widok wskazuje brakującą stronę; użytkownik może jawnie wskazać istniejącą parę albo dodać pustą stronę i wpisać rzeczywisty wynik. Nowe dodatkowe pary mają sąsiadującą kolejność L/R, odtwarzalną po zapisie. Dawne nieparzyste/niejednoznaczne układy wymagają decyzji użytkownika. Nie zmieniono kontraktu wyników ani grup/rund.

## Jedna zasada ostatniego wyniku

Identyczne rzeczywiste wartości o tym samym znaczeniu są prezentowane raz, również po dodaniu zwykłych serii indywidualnym edytorem. To był jeden z powodów niespójności: dodatkowy wiersz bez `setId` był traktowany inaczej niż zwykła seria główna wyłącznie przez brak referencji do celu.

Różne wartości, role, strony, grupy, segmenty i istotne rozszerzenia pozostają rozróżnione; wtedy pokazujemy wszystkie serie w rzeczywistej kolejności grup. L/P są oznaczone, dropsety zachowują pełną kolejność segmentów, back-off pozostaje rozróżniony. Sam bilans liczby L/P nie ukrywa braków przy różnych przepisanych seriach. To samo renderowanie obsługuje karty i historię; zwykła edycja, zapis i restart nie zmieniają zasady. Kompresja nigdy nie zmienia rekordów, statystyk ani tonażu.

## Zakończenie ze szkicami

Blokujący alert zastąpiono panelem. Dla poprawnych szkiców dostępne jest **Zapisz wyniki i zakończ**. Niekompletne wartości wskazują ćwiczenie, serię/stronę/segment. Konflikty baz i kilka wersji tego samego ćwiczenia blokują automatyczny zapis, bez wybierania zwycięzcy. Można wrócić do edycji i pobrać zachowane szkice. Odrzucenie wymaga osobnego potwierdzenia; zatwierdzone wcześniej wyniki pozostają w historii.

Kolejność:

1. Poczekać na kolejkę szkiców, odczytać dostępne źródła i pamięć edytora. Awaria obu magazynów szkicu nie usuwa aktualnego wpisu z pamięci.
2. Zweryfikować cały zestaw i przygotować wyniki przed pierwszym zapisem. Kolejność zapisu odpowiada planowi, nie losowej kolejności kluczy.
3. Zapisać pojedyncze wyniki istniejącym protokołem IndexedDB v2: walidacja, CAS, readback i rzeczywisty `strict complete` pozostają obowiązkowe.
4. Ponownie sprawdzić dostępność źródeł i tokeny. Dopiero po utrwaleniu wszystkich wyników wywołać istniejące `finishSession` i czekać na jego potwierdzenie.
5. Dopiero wtedy usuwać dokładnie te szkice z ochroną tokenów i odświeżyć panel. Błąd przed zakończeniem nie usuwa żadnego szkicu.

Identyfikator nowego wyniku i czas pochodzą deterministycznie ze szkicu; istniejąca korekta zachowuje ID i metadane zatwierdzonego wyniku. Po częściowym zapisie i restarcie rozpoznajemy dokładnie równy, już utrwalony wynik, zamiast tworzyć duplikat lub nadpisywać inną wersję.

### Granice atomowości

To sekwencja istniejących transakcji, **nie jedna transakcja całej sesji**. Awaria po pierwszym wyniku pozostawia go prawidłowo zapisanym, sesję aktywną i wszystkie szkice. Ponowienie zapisuje resztę. Nie wykonujemy automatycznego rollbacku historii. Jeśli proces zakończy się po `finishSession`, a przed sprzątaniem, mogą pozostać szkice do świadomego odrzucenia po sprawdzeniu historii.

Kontrole obejmują dostępne źródła i ponowny odczyt tokenów. Nie twierdzimy, że znamy nieprzechwyconą pamięć innych kart; nowa karta może utworzyć szkic po ostatnim odczycie. Takiego szkicu nie usuwa sprzątanie naszego zestawu. Nie dodano blokady/protokołu współpracy wielu kart. CAS zapisów wyników i zakończenia pozostaje bez zmian.

Pusty lokalny edytor jest stanem do odzyskania, nie wynikiem. Wspólny walidator dowodów v6 zachowuje dotychczasowy kontrakt; nie rozszerzono kodeków/formatów backupów.

## Pomiary

Chromium/Linux, CPU ×4, syntetyczne izolowane profile, 390 px, bez sieciowych operacji Drive. Każdy wariant ma **n=3**, empiryczne p95 jest maksimum. To nie Pixel 9 ani dowód osiągnięcia celu Androida. Nie odrzucano wolniejszych prób.

Przed: `de84e63`. Po: końcowy mechanizm tego PR. [Pełne próbki, zegary, hashe i orakle](performance/workout-finish.json). Bazowy zakończony pomiar zachowano, zamiast go powtarzać. Po doprecyzowaniu walidacji prezentacji zmierzono końcowy runtime ponownie. Późniejsze korekty obejmują tekst potwierdzenia odrzucania oraz zbędny prompt przy pierwszym wpisie do nietkniętego L/P. Nie zmieniają mierzonej ścieżki zapisu/zakończenia; przygotowanie benchmarku używa ćwiczeń obustronnych. JSON jawnie zapisuje hashe zmierzonych plików i tych korekt.

| Scenariusz | Przed: mediana / p95 klik → native strict complete | Po: mediana / p95 |
| --- | --- | --- |
| 4 historyczne sesje, 3 wyniki już zapisane | 120,5 / 132,5 ms | 111,7 / 113,2 ms |
| 40 sesji, raw 4 MiB i checkpointy, 3 wyniki już zapisane | 131,8 / 148,2 ms | 136,2 / 149,3 ms |
| 4 sesje, zapis 3 szkiców i zakończenie | Brak takiej operacji — stary alert blokuje zakończenie | 415,9 / 490,1 ms |
| 40 sesji + raw, zapis 3 szkiców i zakończenie | Brak takiej operacji | 529,6 / 571,1 ms |

Zegar trwałości to pierwszy natywny callback transakcji `strict complete`, z zachowanym `event.timeStamp`, nie toast. Zwykłe zakończenie ma jedną transakcję protokołu, trzy szkice + zakończenie cztery. Metadane sprzątania mają dodatkowe transakcje po utrwaleniu sesji.

Mediany etapów po zmianach (ms):

| Etap | 4 sesje + 3 szkice | 40 sesji + 3 szkice |
| --- | --- | --- |
| Weryfikacja i materializacja wszystkich szkiców | 7,3 | 7,3 |
| Utrwalenie 3 wyników, wraz z walidacją/CAS/readback | 304,2 | 398,3 |
| Zakończenie sesji do potwierdzenia API | 76,2 | 92,3 |
| Pierwszy render po potwierdzeniu sesji | 12,7 | 12,0 |
| Od zdarzenia complete sesji do ostatniego complete sprzątania | 50,1 | 47,8 |
| Końcowy DOM po sprzątaniu | 7,8 | 7,7 |
| Klik → końcowy DOM | 474,3 | 585,1 |

Przedziały API są inkluzywne; median nie należy dodawać jako jednej próbki. Dla dużego wariantu przygotowanie ostatniej komendy przed aktualizacją indeksu zajmuje 32,2 ms, sama transakcja finish 30,2 ms, a inkluzywny odczyt kontrolny 7,8 ms (część transakcji). Czyszczenie liczono na natywnych `event.timeStamp`: callback obserwatora może być wywołany po kontynuacji Promise, więc jego `performance.now()` nie jest wcześniejszym zegarem commit. Oba zegary zachowano w JSON. Gotowy DOM nie jest pomiarem fizycznego wyświetlacza ani klatek telefonu.

Zwykły odczyt/kolejka szkiców przed zakończeniem bez szkiców: mediana 1,6 / 2,4 ms. Największy zmierzony koszt nowego przepływu to rzeczywiste transakcje wyników, nie render. Duży raw pozostaje w bazie; nie jest parsowany/serializowany przez nowy kontroler finish. Orakle po zmianach potwierdzają niezmienność dawnych wyników, modeli, snapshotów i archiwów oraz zakończenie bez pozostawionych szkiców. Nie zmieniono protokołu w celu pozornego skrócenia czasu.

Heap po operacji z instrumentacją i kopią danych do orakli: około 31 MiB dla małej bazy i 496 MiB dla dużej. To **nie** szczyt RAM/RSS ani miara samej aplikacji: benchmark wymusza pełny odczyt historii i archiwów do sprawdzenia niezmienności, wstrzykuje fixture ok. 50 MiB i zachowuje kopię porównawczą. Presji GC/pamięci na fizycznym telefonie nie rozstrzygnięto.

Nie odtworzono wielosekundowego finish na tym zestawie. Nie ma podstaw, by przypisywać zgłoszenie instalacji PWA ani deklarować naprawy czasu telefonu. Dawne nierozstrzygnięte p95 zapisu z PR #97 pozostaje odrębnym wynikiem; nowe liczby mierzą zakończenie/trzy szkice, nie tamten benchmark pojedynczego zapisu.

### Odtworzenie i Pixel 9

`scripts/measure_finish.py --fixtures <katalog syntetycznych fixture protokołu v2> --output <nowy katalog> --repeats 3 --cpu 4`. Użyto zachowanych fixture A–E `small` i `history40-raw4`; ich SHA-256 są w raporcie. Brakujące dane syntetyczne można wygenerować istniejącymi helperami `artifact`/`fixture` w `scripts/measure_incremental_write.py`, w izolowanych profilach: odpowiednio 4/40 sesji, raw 0/4 MiB. Nie uruchamiać generatora na profilu użytkownika. `--after-only` przyjmuje zakończony raport niezmienionej bazy i mierzy jedynie nowe pliki. Uruchamiać bez równoległych lokalnych testów.

Po przeglądzie i wdrożeniu przez właściciela: sprawdzić numer release w Dane; offline wykonać niezależne L/P, usunąć pierwszą parę, dodać parę, anulować i potwierdzić asymetryczne scalanie, wznowić szkic po zamknięciu. Porównać tonaż. Osobno zakończyć sesję z 0, 1 i kilkoma poprawnymi szkicami oraz z pustą wartością/konfliktem. Nie resetować bazy. W DevTools Performance zebrać etapy `pushpull-finish-*`; mark `session-durable` jest po odpowiedzi istniejącego API, a nie wcześniejszym tostem. Rzeczywiste native complete można rejestrować wyłącznie diagnostycznym obserwatorem transakcji jak w skrypcie. Zapisać medianę/p95 z większej próby i rozmiar/strukturę bazy. Dopiero to rozstrzygnie odczuwalne opóźnienie Pixela.

## Weryfikacja i zachowane funkcje

Lokalnie pełny Node **228/228 PASS**. Kolejna ochrona kopiowania dodatkowych segmentów: **5/5 PASS**. Matrix + zakończenie: **14/14 PASS**; następnie **6/6 PASS** obejmujące statystyki/zmiany planów, restart scalonego szkicu i aktualizację PWA ze starą asymetrią. Osobne próby quota, abort drugiego wyniku i abort finish potwierdziły zachowanie szkiców, aktywną sesję po błędzie i idempotentne ponowienie po restarcie. Sprawdzono legacy przy awarii obu magazynów szkicu, offline, 360/390/412 px, serie identyczne 2/3/8, mieszane, back-off/drop, metadane, 1/2/3 pary i brakującą stronę. Zachowano dokładne asercje historycznych rekordów, snapshotów, modeli i tonażu; dostosowano tylko interakcje do niezależnych stron i nowej prezentacji.

Build produkcyjny i worker/hash PASS; brak wdrożenia. W toku prac poprawiono m.in. niezgodny znak w identyfikatorze nowego wyniku, próbę klonowania referencji DOM edytora i injector testowy (nowy rekord używa `add`, nie `put`). Wczesną próbę PWA przerwano po zmianie plików podczas instalowania workera; końcowe testy pracują na niezmiennych plikach/artifactach. Nie uznano tych prób za dowód sukcesu.

Końcową pełną regresję Node/Chromium/PWA, backupów, CAS, restartu i aktualizacji wykonuje wymagany workflow PR; status i link konkretnego commitu są w PR. Brak fizycznego testu Androida i prawdziwego konta Drive.

Zachowano pozostały wygląd Compact Matrix, przyrostowy zapis, schemat IndexedDB v2, CAS/readback/strict complete, historię, archiwa, plany, rotację, statystyki, kopie i Drive. Bez automatycznego kasowania danych, scalania i wdrażania.
