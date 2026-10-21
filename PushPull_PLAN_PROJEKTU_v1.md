# PushPull — plan wdrożenia aplikacji

**Status:** zatwierdzona specyfikacja, 21.10.2026  
**Zatwierdzony wzorzec interfejsu:** PushPull v0.3 Matrix — szlif 3.  
**Cel:** stabilna mobilna aplikacja PWA (Android) do dziennika treningowego i statystyk progresji.

## Reguła nadrzędna

Rozwijamy istniejący kod i interfejs v0.3 Matrix — szlif 3. Nie budujemy od zera kolejnych makiet. Zmiany wizualne dopiero po użytkowaniu i zgłoszeniu konkretnych uwag. Nowe wersje nie mogą usuwać już zatwierdzonych funkcji.

## Wymagania funkcjonalne

1. **Treningi:** PUSH A → PULL A → PUSH B → PULL B; ręczny wybór; automatyczna rotacja po zakończeniu; możliwość wyboru daty; „Rozpocznij trening” i „Zakończ trening”. Bez stałego harmonogramu tygodniowego.
2. **Kalendarz i historia:** oznaczenia wykonanych treningów; przeglądanie i edycja dat oraz wyników zapisanych sesji, bez duplikowania i niezamierzonego przesuwania rotacji.
3. **Karty ćwiczeń:** zwinięte domyślnie; nazwa, opcjonalny opis/wariant, liczba planowanych serii, powtórzenia, tempo i RIR; poniżej ostatni wynik. Gdy wszystkie serie identyczne, wynik skrócony; gdy różne, rozpisane wszystkie serie z ciężarem i powtórzeniami. Tempo ze spacjami, bez myślników.
4. **Wprowadzanie wyników:** domyślnie tylko jeden ciężar i liczba powtórzeń, które automatycznie wypełniają wszystkie zaplanowane serie; ołówek rozwija listę serii z gotowymi danymi, umożliwia poprawki oraz dodanie/usunięcie serii. Indywidualnych poprawek nie można nadpisywać po cichu. Obsługa back-offów; docelowo dropsetów i superserii. Tonaż obliczany z zapisanych serii.
5. **Notatki:** instrukcja trenera oddzielna od notatek użytkownika. Puste pole ma jedną linijkę; zwiększa wysokość wraz z wpisanym tekstem, bez przewijania wewnętrznego.
6. **Statystyki na poziomie ćwiczenia:** osobne klikalne kafelki tonażu, ciężaru, powtórzeń i tempa progresji, każdy z własnym wykresem i tabelą. Historia modyfikacji ćwiczenia, kropki i pionowe znaczniki na wykresach, daty i opisy. Zmiana kąta, maszyny, opisu lub poprawa techniki zachowuje ID i całą historię ćwiczenia, bez mieszania danych między ćwiczeniami. W analizie można odróżnić okresy sprzed i po zmianie, bo nie wszystkie wyniki są bezpośrednio porównywalne.
7. **Dane i plany:** stabilne identyfikatory ćwiczeń, wersje parametrów planu i oryginalne dane każdej sesji; możliwość przyszłych planów V3 itd. bez niszczenia historii V2.
8. **Wygląd:** zatwierdzony motyw Matrix, kompaktowy mobilny interfejs.

## Weryfikacja planu źródłowego

Oryginalny dokument V2: https://docs.google.com/document/d/1gc-kRsciOapQRkiUGugmCSVcsEd5G3QpIgjchTRA-zc/edit

Przed oddaniem aplikacji do codziennego użytku zweryfikować w nim nazwy ćwiczeń, kolejność, liczbę serii, powtórzenia, tempo, RIR i wskazówki techniczne. Makietowe wartości są przykładowe.

## Kolejność wdrożenia

### 1. GitHub + Codex
- Utworzyć jedno repozytorium PushPull i umieścić w nim **rzeczywisty kod** zatwierdzonego szkicu v0.3 Matrix — szlif 3 (najpierw sprawdzić dostępność kompletnych plików).
- Uporządkować kod, wersjonowanie, dokumentację i testy regresji.

### 2. Trwała baza danych
- IndexedDB offline-first: ćwiczenia, plany i ich wersje, sesje, serie, notatki, historia zmian.
- Eksport i import JSON z walidacją i możliwością odtworzenia backupu.
- Nigdy nie traktować samej pamięci przeglądarki jako bezpiecznej kopii zapasowej.

### 3. Weryfikacja rzeczywistego planu V2
- Porównać dane aplikacji z oryginałem od trenera; uwzględnić back-offy i nietypowe układy serii.

### 4. Testy
- Start i zakończenie sesji, rotacja, kalendarz, poprawianie historii, serie różniące się liczbą powtórzeń/ciężarem, tonaż, statystyki, zmiany techniki, działanie offline.
- Test ponownego uruchomienia, aktualizacji PWA i przywracania kopii.

### 5. Publikacja PWA
- Hosting HTTPS (np. GitHub Pages), manifest i service worker; instalacja na Androidzie; testy na realnym telefonie.

### 6. Google Drive
- Dopiero po stabilnym działaniu offline i kopiach JSON wdrożyć synchronizację/kopie na Drive, autoryzację, rozwiązywanie konfliktów i odtwarzanie po zmianie telefonu.

## Warunki gotowości do codziennego użytkowania

- Zapisane treningi i serie przetrwają zamknięcie i uruchomienie aplikacji.
- Edycja historii nie powoduje duplikatów ani błędów rotacji.
- Obliczenia bazują na rzeczywistych danych; braki danych są jawnie sygnalizowane.
- Działa offline oraz eksport i odtwarzanie kopii JSON.
- Plan V2 jest zweryfikowany z dokumentem trenera.
- Aktualizacje nie kasują danych.

## Podział pracy

- **ChatGPT w projekcie:** ustalenia, priorytety, specyfikacje i przegląd poprawek.
- **Codex:** kod, repozytorium GitHub, testy, naprawy, migracje danych, kontrola regresji.
- **Work:** wieloetapowe audyty, weryfikacja źródła V2, przegląd kompletności funkcji, pomoc we wdrożeniu i dokumentacja.
- **GitHub:** wersjonowanie i możliwość przywrócenia starszej wersji.

## Zasady dalszych zmian

Każdą nową uwagę po wdrożeniu opisać jako osobne zadanie z oczekiwanym zachowaniem i testem. Nigdy nie poprawiać wyglądu kosztem utraty zapisanych danych. Nie udawać, że prototyp i finalna implementacja są tym samym.

**Najbliższy krok:** założyć repozytorium GitHub, przenieść do niego zweryfikowany kod zatwierdzonego szkicu, a następnie zlecić Codexowi implementację bazy offline i testów.
