# PushPull — zasady pracy

## Źródło prawdy i zakres
Przed pracą przeczytaj PushPull_PLAN_PROJEKTU_v1.md. Pracuj wyłącznie w MixEEr0700/PushPull. Nie modyfikuj innych repozytoriów, szczególnie KRAK-Previo-API.

## Punkt wyjścia
Rozwijaj rzeczywisty kod PushPull v0.3 Matrix — szlif 3. Nie twórz nowej aplikacji ani zamiennej makiety. Nie zmieniaj zatwierdzonego interfejsu bez polecenia użytkownika. Najpierw sprawdź kompletność źródeł, zasobów i zależności, uruchom bazową wersję i udokumentuj jej stan. Jeśli kodu brakuje, zgłoś blokadę i poproś o kompletne źródła.

## Integralność danych
Zachowaj sesje, wyniki serii, notatki, statystyki i historię zmian techniki. Stabilne ID ćwiczeń, wersje planów i oryginalne parametry sesji są obowiązkowe. Przed migracją zabezpiecz kopię danych, zwaliduj migrację i odtwarzanie. Nie nadpisuj ręcznych poprawek serii ani danych źródłowych bez upoważnienia. Instrukcje trenera i notatki użytkownika pozostają oddzielne.

## Kolejność
1. Import i audyt zatwierdzonego kodu; dokumentacja uruchomienia i bazowe testy regresji.
2. IndexedDB offline-first oraz eksport/import JSON z walidacją i odtworzeniem backupu.
3. Weryfikacja parametrów V2 z dokumentem trenera wskazanym w specyfikacji; nie uznawaj wartości makietowych za dane treningowe.
4. Testy regresji i trwałości danych.
5. Dopiero po testach przygotowanie publikacji PWA przez HTTPS, manifestu i service workera, sprawdzenie na Androidzie.
6. Synchronizacja Drive dopiero po stabilnym offline i backupach JSON.

## Weryfikacja przed publikacją
- Start/zakończenie, wybór daty i rotacja PUSH A → PULL A → PUSH B → PULL B.
- Edycja historii bez duplikatów i niezamierzonej zmiany rotacji.
- Serie wspólne i indywidualne, back-offy, dodawanie/usuwanie serii i tonaż liczony z zapisanych serii.
- Osobne wykresy i tabele, zachowanie ID i oznaczenie zmian techniki.
- Trwałość po ponownym uruchomieniu, działanie offline, aktualizacja PWA bez utraty danych.
- Eksport/import JSON, odrzucanie wadliwych danych bez uszkodzenia obecnej bazy, przywracanie kopii.
- Zgodność interfejsu z zatwierdzonym wzorcem na telefonie.

Po każdym zadaniu podaj: co zmieniono, co zachowano, rzeczywiście wykonane testy i wyniki, ograniczenia. Nie deklaruj gotowości na podstawie samej implementacji. Dopasuj narzędzia, build i CI do otrzymanego kodu; nie zgaduj stosu technologicznego.

### GitHub Actions: oszczędność zasobów i bezpieczeństwo CI

- Nie uruchamiaj zbędnych przebiegów GitHub Actions.
- Nie konfiguruj zdublowanych wyzwalaczy push i pull_request dla tej samej zmiany.
- Każdy PR musi przejść wymagane kontrole przed scaleniem.
- Nowe commity PR powinny anulować wcześniejsze nieaktualne przebiegi tego samego PR.
- Przebiegi różnych PR oraz gałęzi main muszą być od siebie niezależne.
- Nie powtarzaj pełnej regresji bez uzasadnienia.
- Nie uruchamiaj ponownie zakończonych sukcesem testów bez konkretnej potrzeby.
- Podczas pracy wykonuj adekwatne testy lokalne, jeśli pozwala na to środowisko.
- Przed zmianą workflow sprawdź wpływ na wymagane status checks, bezpieczeństwo danych i zużycie minut.
- Nie ograniczaj zakresu testów integralności danych, backupów ani przywracania w celu oszczędzania minut.
- Nie zmieniaj Billing, limitów ani budżetów bez jednoznacznej zgody właściciela.
- Traktuj powyższe zasady jako trwałe wymagania dla kolejnych prac.
