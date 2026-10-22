# Automatyczne szkice i wznowienie treningu

Wymaga kodu PR #10. Jego CI przeszło; w momencie rozpoczęcia prac PR pozostawał otwarty. Ta zmiana nie scala #10 ani nie publikuje aplikacji.

Każda edycja wyniku i struktury serii zapisuje **szkic**, bez dodatkowego przycisku. Dotyczy to także niepełnych/jeszcze niepoprawnych kg i powtórzeń, back-offów, ID serii, segmentów dropsetu, stron L/P i konwencji ciężaru. Szkic nie jest zatwierdzonym wynikiem i nie zasila historii ani statystyk. Samo rozwinięcie edytora nie tworzy szkicu.

Po odświeżeniu lub ponownym otwarciu na ekranie Trening pojawią się „Niedokończone wpisy · szkice lokalne”. **Wznów szkic** otwiera właściwą kartę i formularz rozpoczętej sesji; szkic korekty dawnej sesji otwiera kalendarz. Po wznowieniu normalnie edytuj i zatwierdź wynik. Inne ćwiczenia mają własne szkice i wznawia się je niezależnie. **Odrzuć szkic** zawsze wymaga potwierdzenia. Kopię wybranego szkicu można pobrać jako osobny JSON.

Narciarz (`PULL-B-6A`) i Szrugsy (`PULL-B-6B`) są dwiema zwykłymi kartami, każda z własnym formularzem, szkicem i wynikiem. To tylko etykiety prezentacji: zachowano tożsamości `PULL-B-6-SKI` / `PULL-B-6-SHRUGS`, grupę, dwie rundy, 8–10 dla obu i instrukcję 15 s między członami. Bez przebudowy modelu, wyników lub historycznych snapshotów.

Szkic porównujemy z sesją, snapshotem, wersją planu, pozycją/wariantem i dokładnym zatwierdzonym wpisem, od którego rozpoczęto edycję. Starszy/niezgodny szkic nie nadpisuje wyniku: zostaje oznaczony jako konflikt, można go pobrać i ręcznie odzyskać wartości. Osobne strony/karty przeglądarki dostają odrębne ID szkiców; wznowienie i dalsza edycja również nie nadpisują kopii nadal otwartej w innej karcie.

## Zapis i usuwanie

- Istniejąca baza `pushpull`, wersja 1, sklep `meta`, rekordy `workout-draft:<uuid>`. Bez nowej bazy, migracji ani zmian źródłowej historii/modelu. Ścisła trwałość i odczyt kontrolny; status sukcesu dopiero po `transaction.oncomplete`.
- Przed czekaniem na transakcję najnowszy pełny formularz trafia synchronicznie do bufora `pushpull_workout_draft_v1:<uuid>:<token>` w localStorage. Oryginalny klucz historii pozostaje nietknięty. Każda wersja ma własny klucz, aby sprzątanie nie mogło usunąć nowszej edycji z innej otwartej karty. Bufor danej wersji i starszych, pokrytych nią wersji znika dopiero po utrwaleniu w IndexedDB. Przy uruchomieniu wybierana jest nowsza pełna wersja szkicu; nie zakładamy, że przerwana transakcja się udała.
- Oficjalny wynik nadal zapisuje istniejący mechanizm z walidacją źródła i modelu v3. Po jego powodzeniu usuwamy wyłącznie szkic tego formularza, z kontrolą tokenu/wersji. Jeśli zamknięcie przerwie samo sprzątanie, może zostać nadmiarowy szkic oznaczony jako konflikt; nie jest automatycznie nakładany na zapisany wynik.
- Błąd zatwierdzenia zachowuje szkic i stabilne ID; ponowienie nie tworzy dodatkowych serii. Przy braku miejsca w IndexedDB pozostaje bufor. Jeśli oba zapisy zawiodą, formularz mówi **„Nie utrwalono szkicu — nie zamykaj strony”** i pozwala pobrać nieutrwalony szkic.
- Zakończenie sesji jest blokowane, gdy ma ona niezapisane szkice: najpierw zatwierdź wyniki albo świadomie odrzuć wybrane szkice. Nie usuwamy ich samym przyciskiem „Zakończ”. Zakończona sesja i zatwierdzone dane nadal przechodzą istniejącą weryfikację transakcyjną.
- Import oficjalnej kopii nie usuwa szkiców; niezgodne wpisy zostaną odseparowane do odzyskania. Pełny eksport v3 pozostaje kopią zatwierdzonych danych. Szkice pobiera się oddzielnie przyciskiem odzyskiwania; sam v3 nie jest kopią niezapisanych formularzy.

## Faktyczna weryfikacja i ograniczenia

Cztery przepływy w `tests/test_workout_drafts.py`, na syntetycznej bazie: serie/back-off → zamknięcie → wznowienie, konflikt i potwierdzane odrzucenie; dropset → zabicie procesu renderera Chromium bez unload → odtworzenie oraz L/P → odświeżenie; zapis A przy niezapisanym B → ponowne otwarcie offline → odzyskanie B; błąd zatwierdzenia i kolejnego zapisu szkicu → odzyskanie nowszego bufora → ponowienie bez nowych ID/duplikatów. Wcześniejsze testy zachowują kontrolę historii, pełnych kopii, transakcji, aktualizacji PWA i zgodności Matrix. Końcowe wyniki lokalne i CI są w PR.

Nie wykonano testu na fizycznym Androidzie. To ochrona lokalna, bez chmury: usunięcie danych originu/profilu lub awaria urządzenia może usunąć obie kopie. Nie można zagwarantować zachowania znaku, którego przeglądarka nie zdążyła przekazać do obsługi, ani zapisu przy jednoczesnej niedostępności obu pamięci. Nie ignoruj komunikatu o nieutrwalonym szkicu; pobierz JSON przed wyjściem. Nie wykonywano operacji na prawdziwej historii właściciela ani wdrożenia.
