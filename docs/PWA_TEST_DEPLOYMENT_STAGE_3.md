# Etap 3 — prywatne wdrożenie testowe PWA

Baza: `main` po PR #2, `120b8547b31926705e75079c69109c06cac9f9c8`. Repozytorium `MixEEr0700/PushPull` jest prywatne; przed pracą `has_pages=false`. Ten etap nie włącza hostingu, nie zmienia widoczności, nie dodaje kont/chmur/sekretów i nie publikuje aplikacji. Plan V2 nadal wymaga weryfikacji z dokumentem trenera. To wersja testowa, nie zatwierdzona do codziennego użytku.

## Rekomendacja i koszt

Najprostszy wariant **prywatnego testu osobistego**: istniejący komputer właściciela → serwer statyczny nasłuchujący tylko na loopback → **Tailscale Serve** → Chrome na Androidzie w tym samym tailnecie. Nie wymaga publicznego VPS, przekierowania portów routera ani przenoszenia repozytorium. Tailscale terminuje HTTPS; aplikacja nadal nie wysyła treningów do serwera.

| Wariant | Repozytorium może pozostać prywatne | Dostęp do witryny | Koszt i ograniczenia |
| --- | --- | --- | --- |
| Własny komputer + Tailscale Serve — rekomendowany | Tak, repo nie jest serwowane; można użyć samej paczki runtime | Tylko urządzenia/osoby dopuszczone w tailnecie i jego regułach dostępu | Sam serwer statyczny: **0 zł opłaty hostingowej**, plus własny sprzęt, prąd i Internet. Konto Tailscale według aktualnego planu; przed uruchomieniem sprawdzić możliwość użycia Personal i jego bieżące warunki. Komputer musi działać przy pierwszym wejściu i aktualizacji. Android wymaga klienta Tailscale. |
| GitHub Pages | Tak, ale Pages z prywatnego repo wymaga odpowiedniego planu, np. Pro/Team/Enterprise | **Prywatne repo nie oznacza prywatnej witryny.** Prywatne publikowanie z kontrolą dostępu dotyczy witryn projektowych organizacji Enterprise Cloud | Zależne od planu GitHub. Nie zakładamy posiadania Pro/Enterprise i nie kupujemy planu. Dla tego osobistego repo nie wybieramy Pages jako domyślnie prywatnego hostingu. |
| Cloudflare Pages | Tak, również przez ręczne przesłanie samego artefaktu bez udostępniania Git | Domyślnie publiczne. Access dla preview nie dowodzi ochrony produkcyjnego adresu i wszystkich aliasów | Statyczne żądania w planie Free: **0 USD**, w granicach zasad/limitów platformy. Pełna prywatna konfiguracja Access i ochrona wszystkich wejść wymaga osobnego przygotowania i weryfikacji. Nie została wdrożona. |

Nie podajemy niepotwierdzonych bieżących limitów/liczby użytkowników ani ceny płatnego planu Tailscale/GitHub. Strona cennika Tailscale była w tej sesji zablokowana przez proxy (403); nie potwierdzono aktualnej ceny ani limitów Personal. **0 zł powyżej dotyczy własnego serwera, nie gwarancji darmowej subskrypcji VPN.** Przed aktywacją sprawdzić [aktualny cennik Tailscale](https://tailscale.com/pricing). Dodatkowy koszt GitHub Actions i artefaktów zależy od limitów istniejącego konta; lokalna budowa ich nie zużywa.

Ograniczenia rekomendacji:

- Serve oznacza dostęp wewnątrz tailnetu. **Nie używać `tailscale funnel`**, które udostępnia serwer w Internecie.
- Nie instalujemy klienta VPN w zarządzanym środowisku Codexa. Poniższe kroki dotyczą własnego komputera użytkownika i wymagają osobnej decyzji o uruchomieniu.
- Zasady tailnetu muszą dopuszczać wyłącznie właściwe urządzenia/osoby i port usługi. Domyślna szeroka reguła tailnetu nie jest automatycznie upoważnieniem wszystkich członków do aplikacji. Nie zastępować istniejących ACL w ciemno.
- Tailscale używa systemowego miejsca na VPN Androida; może kolidować z innym VPN. Po pierwszej poprawnej instalacji cache pozwala testować offline także bez połączenia z serwerem; aktualizacje wymagają ponownego dostępu.
- Certyfikat wymaga włączenia HTTPS w tailnecie. Publiczne logi Certificate Transparency mogą ujawnić nazwę DNS urządzenia; nadać neutralną nazwę, np. `pushpull-test`, bez danych osobowych.
- Nie obiecujemy wygenerowania WebAPK dla prywatnego adresu. Zależność od wersji Chrome, sieci i procesu pakowania trzeba sprawdzić na fizycznym telefonie. Skrót do strony nie jest automatycznie potwierdzeniem pełnej instalacji PWA. Nie włączać publicznego hostingu tylko po to, by wymusić instalację.
- Uprawniony tester otrzymuje kod HTML/CSS/JS jak w każdej aplikacji webowej. Prywatne repo pozostaje prywatne, ale przeglądarka musi otrzymać kod runtime. Cofnięcie dostępu sieciowego nie usuwa kopii offline ani danych z telefonu.

## Przygotowany artefakt — bez publikacji

```sh
python3 scripts/build_release.py --check
python3 scripts/build_release.py --output dist/releases/test-001
```

`--check` kontroluje zgodność śledzonego `sw.js` z zasobami i szablonem. Budowa kopiuje wyłącznie: `index.html`, `style.css`, `app.js`, `storage.js`, `indexeddb.js`, manifest, SVG, trzy PNG, wygenerowany worker i `release.json`. Nie kopiuje `.git`, dokumentacji, fixture'ów, skryptów, eksportów JSON ani konfiguracji konta. Brak bundlera i zależności npm. `dist/` jest ignorowany przez Git. `.gitattributes` utrzymuje LF, aby konwersja końców linii przy checkout na Windows nie rozjeżdżała sum kontrolnych.

Budowa jest powtarzalna. Nie nadpisuje obcych plików ani zmienionej istniejącej paczki. Nową wersję budować w **nowym katalogu**, nigdy przez podmienianie plików w aktywnie serwowanym katalogu. Ponowne zbudowanie identycznej paczki jest dozwolone. Zmianę runtime zatwierdzać razem z odświeżonym workerem:

```sh
python3 scripts/build_release.py --refresh-worker
python3 scripts/build_release.py --check
```

`scripts/serve_test.py` sprawdza kompletną listę plików i SHA-256 przed startem, odmawia serwowania checkoutu/zmodyfikowanej paczki i nasłuchuje tylko na `127.0.0.1`. Nie ma listingu katalogów ani endpointu wysyłania danych. Ścieżki spoza listy runtime, w tym `.git`, dokumentacja i JSON backupów, zwracają 404. Stosuje poprawne MIME, `no-cache`, CSP, `nosniff`, zakaz iframe, brak referera i HSTS dla połączenia przez HTTPS. HTTP na loopback jest zapleczem proxy, nie adresem instalacji na telefonie.

Workflow `.github/workflows/test-artifact.yml` ma **wyłącznie ręczny `workflow_dispatch`**: przygotowuje paczkę jako prywatny artefakt Actions na 7 dni. Nie ma uprawnień Pages, kroków deploy, tokenów hostingu ani automatycznego uruchomienia po merge. Może pojawić się w menu Actions dopiero po zatwierdzeniu workflow na gałęzi domyślnej. Nie został ręcznie uruchomiony w tym etapie. CI regresji osobno buduje i sprawdza paczkę, bez hostowania.

## Uruchomienie prywatnego HTTPS — dopiero po decyzji użytkownika

Instrukcje są też w `deploy/tailscale-serve.example.sh`; uruchomienie tego pliku samo **nie włącza** hostingu.

1. Na własnym komputerze mieć Python 3, aktualny Tailscale, konto z właściwymi uprawnieniami oraz poprawnie skonfigurowany tailnet/HTTPS. Nie kopiować kluczy do repozytorium. Sprawdzić istniejące `tailscale serve status` oraz reguły dostępu, zanim zmieni się mapowanie portu.
2. Zbudować wybraną zatwierdzoną wersję do nowego katalogu. W terminalu 1 uruchomić:

   ```sh
   python3 scripts/serve_test.py --directory dist/releases/test-001 --port 8000
   ```

3. W terminalu 2, po świadomym zatwierdzeniu prywatnego testu, wykonać:

   ```sh
   tailscale serve --bg --https=443 http://127.0.0.1:8000
   tailscale serve status
   ```

   Wynik ma mówić **Available within your tailnet**, nie „Available on the internet”. Nie omijać weryfikacji TLS i nie używać `https+insecure`. Nie wykonywać `serve reset`, jeśli komputer ma inne usługi. Powyższe mapowanie może zastąpić istniejący handler portu 443 — najpierw sprawdzić jego właściciela i przeznaczenie.

4. Zanotować dokładny HTTPS URL pokazany przez Tailscale. Używać go stale — nie wymyślać adresu na podstawie nazwy przykładowej. Dopuścić do tej usługi tylko testerów. Repozytorium i Pages pozostają bez zmian.
5. Po zakończeniu testu można wyłączyć własne mapowanie `tailscale serve --https=443 off`, po sprawdzeniu że nie usuwa innej potrzebnej usługi, i zatrzymać własny serwer Python. Nie usuwa to IndexedDB na telefonie.

## Aktualizacja bez zmiany origin

1. Na telefonie zapisać trening i wykonać pełny eksport JSON poza przeglądarkę. **Niezapisane drafty są tylko w pamięci** i zostaną utracone przy świadomym zamknięciu okna.
2. Zbudować następny zatwierdzony commit do nowego katalogu, np. `dist/releases/test-002`. Sprawdzić paczkę i testy przed zmianą serwera.
3. Zatrzymać wyłącznie własny proces Pythona i uruchomić go z nową paczką na **tym samym porcie 8000**. Mapowanie Serve i HTTPS hostname pozostają te same. Nie przesyłać nowej wersji plik po pliku do działającego katalogu.
4. Przy dostępie do sieci otworzyć aplikację, aby przeglądarka wykryła nowy worker. Nie należy oczekiwać wymuszonego odświeżenia: nowy worker czeka. Zapisać pracę i zamknąć **wszystkie** karty/PWA tej aplikacji. Następnie uruchomić ją ponownie.
5. Sprawdzić historię, dane i offline według checklisty. Gdy brak zasobów nowej wersji, instalacja nowego workera jest odrzucana, a poprzednia działająca wersja pozostaje dostępna. Nie czyścić danych witryny jako „naprawy aktualizacji”.

Worker ma identyfikator wydania wyprowadzony z szablonu i SHA-256 wszystkich zasobów. Pobiera zasoby do osobnego cache każdej próby, odrzuca redirect/logowanie/niezgodne bajty i dopiero po sprawdzeniu kompletu udostępnia cache wydania. Nie stosuje `skipWaiting`, komunikatu wymuszającego aktywację ani automatycznego reloadu dokumentu. Nie wywołuje żadnej operacji na IndexedDB/localStorage. Usuwa tylko tymczasowy cache własnej próby; wcześniejsze cache wydań są zachowane. Jeśli publikacja końcowego cache zostanie przerwana, niekompletny worker nie aktywuje się.

Gdy przeglądarka usunie pojedynczy zasób cache, worker może go naprawić online **tylko po zgodności SHA-256 z działającą wersją**. Offline lub przy niezgodnej wersji zwraca 503; nie miesza starego i nowego kodu i nie inicjalizuje nowej historii. Może zainicjować pobranie kompletnej aktualizacji, nadal czekającej na zamknięcie klientów. Starsze cache mogą zajmować miejsce; nie wykonujemy automatycznego szerokiego czyszczenia. Staging zwiększa chwilowe zapotrzebowanie na miejsce, a quota może zatrzymać aktualizację.

## Origin i bezpieczeństwo historii

IndexedDB i localStorage są przypisane do **schematu + hosta + portu**, nie do repozytorium ani ikonki. Przejście z HTTP na HTTPS, inny host, inny port lub inny profil/telefon oznacza osobny magazyn. Automatyczna migracja v1 działa wyłącznie na tym samym origin. Do przeniesienia danych użyć pełnego eksportu i walidowanego importu, bez kasowania oryginału.

Dwie różne ścieżki na tym samym origin nie izolują IndexedDB. Osobne destrukcyjne testy prowadzić na innym origin/profilu, a nie tylko w innym podkatalogu. Manifest zachowuje `start_url` i jawne `id: ./index.html`, odpowiadające wcześniejszemu domyślnemu identyfikatorowi. Zmiana nazwy DNS urządzenia lub tailnetu może stworzyć nowy origin i pozornie „pustą” instalację. Stara historia nie migruje wtedy automatycznie — pozostaje przy starym adresie.

Zainstalowanie PWA nie jest kopią zapasową ani gwarancją trwałej pamięci. Czyszczenie danych witryny, odinstalowanie, utrata telefonu, polityki systemowe i presja na pamięć mogą usunąć dane. Zachować pełne JSON poza aplikacją; nie polegać wyłącznie na IndexedDB i lokalnym archiwum. Nie zakładamy, że tryb standalone ma zawsze wspólny magazyn z kartą we wszystkich wersjach Androida — należy to sprawdzić fizycznie.

## Źródła sprawdzone i niewykonane czynności

21.10.2026 odczytano oficjalne źródła:

- [GitHub: prywatna publikacja Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/changing-the-visibility-of-your-github-pages-site), weryfikacja przez [źródło GitHub Docs](https://github.com/github/docs/blob/main/content/pages/getting-started-with-github-pages/changing-the-visibility-of-your-github-pages-site.md) oraz [warunek Enterprise Cloud](https://github.com/github/docs/blob/main/data/reusables/pages/privately-publish-ghec-only.md).
- [Dostępność Pages według planu](https://github.com/github/docs/blob/main/data/reusables/gated-features/pages.md).
- [Cloudflare: preview publiczne domyślnie i Access](https://developers.cloudflare.com/pages/configuration/preview-deployments/), [źródło](https://github.com/cloudflare/cloudflare-docs/blob/production/src/content/docs/pages/configuration/preview-deployments.mdx); [ceny żądań statycznych](https://github.com/cloudflare/cloudflare-docs/blob/production/src/content/docs/pages/functions/pricing.mdx).
- [Tailscale Serve](https://tailscale.com/kb/1312/serve): oficjalna strona była blokowana przez proxy, ale [oficjalny kod/help CLI](https://github.com/tailscale/tailscale/blob/main/cmd/tailscale/cli/serve_v2.go) potwierdza rozdzielenie Serve (tailnet) / Funnel (Internet), reverse proxy i tryb `--bg`. [Cennika](https://tailscale.com/pricing) nie udało się odczytać; nie uznajemy go za zweryfikowany.

Nie utworzono kont/usług, DNS, publicznego endpointu, certyfikatu Tailscale, wdrożenia Pages/Cloudflare ani instalacji Android. Lokalne certyfikaty testów HTTPS były jednorazowe i nie trafiły do repozytorium. Instrukcja fizycznego urządzenia: [ANDROID_TEST_CHECKLIST.md](ANDROID_TEST_CHECKLIST.md). Wyniki automatyczne: [STAGE_3_TEST_REPORT.md](STAGE_3_TEST_REPORT.md).
