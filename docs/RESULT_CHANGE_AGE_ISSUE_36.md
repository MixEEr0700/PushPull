# Issue #36 — ostatnia zmiana zapisanego wyniku

Baza: `main` po PR #37 (`fd708b0`). Zmiana wyłącznie odczytu/prezentacji; bez migracji i nowego pola bazy.

Na karcie V2/V3+ pozostaje ostatni faktycznie zapisany wynik wybrany przez niezmienione `lastFor`. Obok jest jedna mała etykieta „Ostatnia zmiana: N sesji temu”. Nie jest to rekord, ranking ani ocena progresu. Szkielet z nieustalonym kontekstem pokazuje „nieustalona”; karta bez wyniku nie ma etykiety. Historia pojedynczej sesji nie otrzymuje dzisiejszego licznika.

## Reguły

- Historia sortowana jak dotąd: data sesji malejąco, następnie `seq`. Korekty historii/dat są uwzględniane przy następnym renderowaniu.
- Tylko zakończone sesje z rzeczywistym wpisem tego ćwiczenia. Szkice, inne ćwiczenia, sesje bez wyniku i bieżący trening nie zwiększają licznika. W trakcie sesji może być już wyświetlony jej zatwierdzony wynik; etykieta nadal dotyczy wcześniejszych zakończonych wykonań (wyjaśnienie w tytule etykiety).
- N to długość najnowszej serii identycznych, porównywalnych wykonań: A/B/C takie same → 3; ostatnie inne niż przedostatnie → 1. Pierwszy wiarygodny wynik jest początkiem serii, bez twierdzenia o poprawie.
- Kontekst pochodzi z zachowanego snapshotu: ID ćwiczenia/wariantu, parametry maszyny/wykonania, strony i znaczenie/jednostka ciężaru. Nie łączymy ćwiczeń po nazwie. Rozpoznane inne konteksty są pomijane; brak wiarygodnego kontekstu przerywa ustalanie wieku, zamiast zgadywać.
- Porównanie obejmuje zapisane serie w kolejności celów, L/P w stałej kolejności, wszystkie segmenty w ich kolejności, role back-off/drop i rundy grup. Zmiana w dowolną stronę, także liczby wykonanych serii/segmentów, jest zmianą. Brak sumowania, wybierania maksimum lub przeliczania kg.
- UUID rekordów, serii, segmentów i celów nie są pomiarem. Dziesiętne zapisy `105`/`105.0` są równe; normalizacja tekstowa nie zaokrągla ciężarów przez konwersję do Number. Inne uwagi, instrukcje, znacznik poprawy techniki i wartości docelowe nie zastępują pomiaru.
- Wyniki niepełne, niezgodne ze snapshotem, o nieokreślonej konwencji kg lub niejednoznacznie powielone w tej samej sesji → „nieustalona”. Nie uzupełniamy starszych danych dzisiejszym planem.

## Zakres kodu i weryfikacji

`model/performance.mjs`: dwie funkcje odczytu/etykiety; walidacja istniejących struktur. `app.js`: dopisek w istniejącym podsumowaniu, bez zmian `lastFor`, formularzy, zapisów i statystyk. `sw.js`: odświeżone hashe istniejącym generatorem. Bez zmian CSS, nawigacji, ID, planów i modułów Drive.

Testy w istniejących narzędziach Node/Playwright obejmują równe zapisy, spadki/wzrosty, L/P, drop/back-off, różne UUID, konteksty, daty/seq, rozdzielne A/B/C i snapshoty importowanych V3/V4. Scenariusz Chromium aktualizuje rzeczywisty service worker z `fd708b0` na nową wersję z trzema zapisami i szkicem, porównuje całą bazę oraz szkice, pracuje offline, zatwierdza spadek, koryguje wynik w kalendarzu i odtwarza pełną kopię JSON na pustym profilu. Renderowanie nie zapisuje niczego w bazie. Pełne wyniki wykonania i CI znajdują się w raporcie PR.

Nie testowano fizycznego Androida ani rzeczywistego konta Google. Wszystkie operacje treningowe i aktywacje w testach dotyczą wyłącznie syntetycznej bazy. Brak aktywacji planu właściciela, publikacji produkcyjnej i automatycznego scalenia.
