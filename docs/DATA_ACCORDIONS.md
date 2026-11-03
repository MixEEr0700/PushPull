# Dane — spójne akordeony po PR #149

## Zmiany

Pięć sekcji ma wspólne nagłówki, wskaźnik rozwinięcia i obszar dotykowy minimum 48 px:

- **Zapisz kopię**: tylko pobranie kompletnej kopii na urządzenie i zapis/ponowienie przyrostowej kopii na Drive. Oba korzystają z istniejącego PPC1, bez technicznego oznaczenia w głównych etykietach.
- **Przywróć kopię**: lokalny plik, Drive, punkty odzyskiwania Drive, istniejący podgląd i potwierdzenie oraz pomocnicze pobranie pliku.
- **Google Drive**: automatyczna kopia po treningu, statusy, logowanie i konfiguracja/odłączenie konta.
- **Punkty cofnięcia**: PPC1 oraz zachowane wcześniejsze kopie ratunkowe i ich bezpieczny podgląd.
- **Narzędzia serwisowe**: historyczny eksport JSON i jego ręczny zapis na Drive, diagnostyka oraz zagnieżdżone narzędzia techniczne/eksperymentalne.

Wszystkie sekcje są początkowo zamknięte. Zapis i przywracanie nadal wzajemnie się wykluczają; anulowanie przy przełączaniu zachowuje dotychczasową obsługę. Stan otwarcia Google i punktów cofnięcia jest zachowany w pamięci UI podczas ponownego renderowania. Nie jest zapisywany w bazie ani localStorage.

## Zachowano

Bez zmian silnika kopii, formatów, transportu Drive, importu, rollbacku, preimage, CAS/readback/strict complete ani modelu danych. Bez migracji lub usuwania danych. Plany, statystyki i aktualizacja PWA pozostają dostępne. Samo otwarcie sekcji nie uruchamia pełnego audytu historii.

## Weryfikacja

Lokalnie: 21 celowanych przypadków Chromium PASS (układ i główne przyciski, pliki i Drive, B1/B2, anulowanie, konflikty rewizji, offline/restart, podgląd ratunkowy). Dwa scenariusze restartu początkowo wymagały otwarcia nowej sekcji Google przed ponownym logowaniem; po dostosowaniu nawigacji oba PASS. Nowy test głównych przycisków potwierdza odczyt wyeksportowanej kopii oraz zweryfikowany upload formatu `pushpull-drive-ppc1`, zamiast historycznego JSON.

Node: 2/2 testy prezentacji statusów PASS. `node --check app.js`, kontrola buildu/SW i hashy PASS. Przed rozszerzeniem o główny format PPC1 zaliczono dodatkowy zestaw 27 przypadków, obejmujący produkcyjny eksport/restore i rollback; nie traktujemy go jako pełnej regresji końcowego commitu. Pełna regresja Node/Chromium/PWA i build są uruchamiane raz w istniejącym GitHub Actions dla końcowego commitu; wiążący wynik znajduje się w PR. Testy zachowują asercje integralności, a nawigacja testowa została dostosowana do nowych lokalizacji kontrolek. Testy mobilne obejmują 360/390/412 px, obsługę klawiatury, brak poziomego przewijania oraz niezmienność IndexedDB/localStorage. Podglądy ratunkowe obejmują offline, anulowanie i konflikt rewizji.

## Ograniczenia

Profile przeglądarki są syntetyczne, a Google API symulowane. Brak odbioru na fizycznym Pixelu 9 i rzeczywistym koncie Drive. To zmiana organizacji UI, bez nowego mechanizmu backupu lub obietnicy poprawy czasu jego wykonania.
