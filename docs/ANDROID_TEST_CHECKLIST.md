# PushPull — instalacja i odbiór na prawdziwym Androidzie

**Status: NIEWYKONANE na fizycznym telefonie.** Desktopowy Chromium i mobilny viewport nie potwierdzają działania Androida ani WebAPK. V2 pozostaje planem wymagającym weryfikacji; testować dane demonstracyjne, nie traktować wersji jako zatwierdzonej do codziennych treningów.

Wyniki wpisać dopiero po wykonaniu: model telefonu, Android, wersja Chrome/Tailscale, data, dokładny origin, release z `release.json`, rodzaj instalacji (WebAPK/PWA/skrót), wynik PASS/FAIL/NIEWYKONANE i opis problemu. Nie dodawać prywatnych JSON, nazw urządzeń zawierających dane osobowe ani kluczy do Git/PR/logów.

## Instalacja — po zatwierdzeniu i uruchomieniu prywatnego hostingu

1. Na komputerze i telefonie połączyć Tailscale z właściwym kontem/tailnetem. Udostępniony serwer musi mieć status „Available within your tailnet”. Nie włączać Funnel ani publicznych portów.
2. Na telefonie w **zwykłym Chrome**, nie incognito ani w przeglądarce wbudowanej komunikatora, otworzyć dokładny HTTPS URL podany przez Serve. Potwierdzić prawidłowy certyfikat i brak ostrzeżeń TLS. Nie używać adresu `localhost`/`127.0.0.1` z komputera na telefonie.
3. Poczekać na pełne pierwsze załadowanie. Jeżeli przenosisz historię z innego origin/urządzenia, najpierw pobrać pełny JSON z oryginalnej aplikacji i zachować go poza telefonem. Nowa domena nie ma automatycznie dostępu do starej bazy. Wczytać kopię w Dane → import, bez kasowania źródła.
4. Menu Chrome → **Zainstaluj aplikację** lub **Dodaj do ekranu głównego** → dostępna opcja instalacji. Potwierdzić nazwę, ikonę i monity. Jeśli dostępny jest wyłącznie skrót, zanotować to osobno; nie oznaczać WebAPK jako PASS. Gdy proces prywatnego adresu nie pozwala zakończyć instalacji, nie publikować strony samodzielnie jako obejścia.
5. Uruchomić z ikony. Sprawdzić tryb standalone, brak zwykłego paska adresu i poprawne krawędzie ikony/maskowania. Porównać historię z kartą Chrome; nie zakładać wspólnego magazynu bez tego testu.
6. Wykonać pełny eksport JSON w zainstalowanej aplikacji. Potwierdzić obecność pliku w Pobranych i możliwość znalezienia go przez systemowy selektor przy imporcie. Kopię zachować również poza przeglądarką/urządzeniem.

## Obowiązkowy odbiór fizyczny — każda pozycja obecnie NIEWYKONANA

| Test | Czynność i kryterium |
| --- | --- |
| Dostęp prywatny / HTTPS | Adres działa na dopuszczonym telefonie; niedopuszczone urządzenie nie pobiera witryny. Brak ostrzeżeń TLS. Zanotować ewentualny konflikt z innym VPN. |
| Instalacja | Potwierdzić rzeczywisty wynik procesu instalacji w danej wersji Chrome, ikonę 192/512, maskowanie koła/squircle i standalone. Skrót zapisać jako odrębny wynik. |
| Zatwierdzony Matrix | Porównać trening, zwinięte/rozwinięte karty, kalendarz i cztery metryki statystyk ze wzorcem szlif 3. Brak zasłonięcia nawigacji przez systemowe paski. |
| Dotyk i klawiatura | Rozwijanie kart, wybór daty, klawiatura liczbowa, ciężar z przecinkiem, zmiana powtórzeń, ołówek, dodanie/usunięcie serii, scroll, powiększanie notatek. Brak zgubienia fokusu i zasłonięcia przycisku zapisu. |
| Rotacja i historia | PUSH A → PULL A → PUSH B → PULL B; start/zakończenie; korekta dawnej daty i serii bez duplikatu i zmiany rotacji. |
| Dane i statystyki | Różne serie, np. 100×10 i 80×8 = 1640 kg; sprawdzić zapisane wartości, cztery metryki oraz notatkę/znacznik techniki. |
| Restart | Zapisać wynik i JSON, zamknąć PWA i Chrome, uruchomić ponownie, potem ponownie uruchomić telefon. Porównać historię/serie/ID przez eksporty. Nie czyścić danych. |
| Offline | Po pełnym załadowaniu odłączyć Internet/VPN lub włączyć tryb samolotowy. Uruchomić z ikony, otworzyć historię, dodać demonstracyjny zapis, zamknąć i uruchomić ponownie; dane mają pozostać. |
| Backup i odtworzenie | Wyeksportować pełny JSON offline; odtworzyć poprawną kopię na odrębnym testowym origin/profilu. Anulować import i spróbować niepoprawnego pliku; aktualne dane pozostają zachowane. Nie niszczyć jedynej oryginalnej bazy w celu sprawdzenia odtwarzania. |
| Aktualizacja w trakcie edycji | Zapisać pełny backup, pozostawić roboczą serię, wgrać zatwierdzoną nową paczkę na serwerze pod tym samym adresem. Brak samoczynnego przeładowania. Zapisać draft przed zamknięciem wszystkich kart/PWA. |
| Aktualizacja po zamknięciu | Zamknąć wszystkie okna starej wersji i uruchomić ponownie. Sprawdzić nowy release, niezmienione IndexedDB, kopie, ID, historię i działanie offline. |
| Nieudana aktualizacja | Na osobnym środowisku testowym zasymulować niekompletną paczkę/brak zasobu. Stara wersja pozostaje używalna; nie wolno resetować magazynu jako obejścia. |
| Pamięć i system | Zanotować zachowanie po ubiciu aplikacji przez Androida, długim uśpieniu i ograniczeniach baterii. Kontrolowany test presji pamięci tylko na danych demonstracyjnych z kopią poza urządzeniem. |

## Gdy coś nie działa

- Brak instalacji: sprawdzić aktualny Chrome, zwykły profil, HTTPS, dostęp przez Tailscale i kompletność zasobów. Zgłosić wersje i wynik, nie obchodzić ostrzeżeń certyfikatu.
- Stara wersja: zapisać pracę i backup, zapewnić dostęp do serwera, zamknąć wszystkie karty/PWA, otworzyć ponownie. Nie odinstalowywać i nie czyścić danych witryny na próbę.
- Pozornie pusta historia: sprawdzić schemat/host/port, profil i urządzenie. Inny origin nie migruje danych automatycznie. Zachować obie instalacje i użyć walidowanego importu kopii.
- Ekran odzyskiwania: pobrać obie dostępne historie/kopie i postępować według [instrukcji etapu 2](INDEXEDDB_MIGRATION_STAGE_2.md). Nie nadpisywać ręcznie bazy.

Pozytywny wynik checklisty nadal nie potwierdza parametrów planu V2 ani gotowości do codziennego użytku — to osobne kryteria projektu.
