# Kompaktowy wynik na kartach — Issue #32

Baza: `main` po PR #33 (`084f470`). Zmiana dotyczy tylko tekstowego podsumowania zapisanych wyników na istniejących kartach oraz historii korzystającej z tej samej funkcji. Bez migracji i zmian modelu, zapisu, planu czy danych użytkownika.

- Wszystkie zwykłe serie i obie strony identyczne: `15 × 105 kg`, bez powtarzania liczby serii i L/P.
- Różne wyniki pomiędzy seriami: osobny wiersz każdej serii.
- Różne L/P tylko w trzeciej: `Seria 1: 15 × 105 kg`, `Seria 2: 15 × 105 kg`, `Seria 3: L 12 × 105 kg · P 14 × 105 kg`.
- Dropset zachowuje kolejność wszystkich segmentów (`12 × 40 kg → 6 × 30 kg`), oznaczenie dropsetu i osobne serie. Back-off pozostaje oznaczony, nawet jeśli wynik jest taki sam jak w serii głównej.
- Znaczące rundy pozostają numerowane. Niezależne karty 6A/6B mają niezależne skróty, zgodnie z dotychczasowym traktowaniem ich jako zwykłych ćwiczeń.
- Starszy format wyników bez strukturalnego wykonania zachowuje listę wyników i metadane sesji; tekst kg/powtórzeń jest ujednolicony, bez dopisywania stron lub odtwarzania celów.

## Parowanie wyłącznie podczas odczytu

Wykorzystujemy istniejące reguły edytora: zgodne `setId`, `groupId`, `round` i jednoznaczne L/P. Kolejność celów jest odczytywana z zachowanego snapshotu, a nie bieżącego planu. Dodatkowe serie `setId=null` łączymy tylko przy jednej jednoznacznej parze. Przy wielu możliwych partnerach rekordy zostają osobno, z informacją „para L/P nieustalona”. Niepełne dane nie są kompresowane do pozornie pełnego wyniku.

Nie zmieniają się `performance.rows`, ID, segmenty, tonaż, liczba serii w statystykach, szkice ani snapshoty. Numer „Seria” w skrócie opisuje cel/wykonanie na karcie — nie zmienia dotychczasowego liczenia osobnych wierszy L/P w statystykach ogólnych. Edytor nadal pokazuje strony oddzielnie i zachowuje istniejące łączenie/rozłączanie.

## Weryfikacja

Testy Node obejmują warianty A/B/C/D, kolejność fizycznych rekordów inną niż kolejność celów, wymagane/opcjonalne L/P, brak partnera, dodatkowe serie, niepełne dane oraz niezmienność wyników, projekcji i szkicu podczas renderowania. Istniejące scenariusze Chromium rozszerzono o dokładne skróty back-off/drop i niezależnych 6A/6B.

Nowy test PWA najpierw odtwarza problem sześciu wierszy na wersji `084f470`, następnie aktualizuje aplikację bez czyszczenia pamięci, sprawdza niezmienność bazy i szkicu L/P, zapisuje odzyskaną korektę oraz sprawdza jej trzy wiersze, historię i dotychczasowy tonaż po restarcie offline.

Pełne wyniki Node/Chromium i stan GitHub Actions: raport PR. Nie testowano fizycznego Androida ani rzeczywistego konta Google; testy używają wyłącznie danych syntetycznych. Issue #34 nie jest częścią tej zmiany.
