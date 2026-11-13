# #165 — rotacja według kalendarza

## Przyczyna i nowe źródło sugestii

Dotychczas `nextType()` odczytywał trwałe nextUnitId/nextType, a finish przesuwał je według właśnie kończonej sesji. Usuwanie szukało największego seq; korekta daty nie aktualizowała wskaźników. Była to kolejność operacji, a nie chronologia kalendarza.

`lastCompleted()` wybiera teraz zgodną z aktywną wersją planu zakończoną sesję o największym session.date. Przy wspólnej dacie rozstrzyga większe seq (stabilny ID jest dodatkowym rozstrzygnięciem; poprawna baza ma unikatowe seq). `nextType()` przechodzi do następnej jednostki z uporządkowanej listy units aktywnego planu; bez pasującej historii wybiera pierwszą. Sesje innych wersji nie uczestniczą. W źródłowym dzienniku bez aktywnej wersji uwzględniana jest dawna historia bez snapshotu lub źródłowe snapshoty niewykonywalnego planu; nie zalicza się snapshotów wykonawczych innych wersji.

Jawna reguła przyszłych dat: zakończone sesje z przyszłą datą biorą udział dokładnie według zapisanej daty. Nie cofamy dat i nie sprawdzamy zegara, więc wynik nie zmienia się samoczynnie po północy. Aktywna sesja jest wykluczona z obliczeń, a jej typ nadal ma pierwszeństwo w UI.

nextUnitId i nextType są zachowane dla zgodności. `advance()` podczas istniejących operacji zapisu aktualizuje je do wyliczonej wartości, lecz odczyt sugestii nigdy na nich nie polega. W przypadku niestandardowych jednostek nie wpisujemy ich do starego nextType, którego kontrakt dopuszcza cztery tradycyjne ID. Nie zmieniono ID, seq, wyników ani dat poza jawnym zapisem daty z istniejącego formularza.

## Natywny zapis i odroczona historia

Szybki start pobiera uwierzytelnione nagłówki sesji wymienionych w katalogu oraz identyfikatory wersji snapshotów potrzebne do wybrania chronologicznego poprzednika. Dołącza jego snapshot do istniejącego selektywnego widoku. Nie opiera sugestii na niepełnej liście ostatnich wyników: sesja bez wyników także uczestniczy. Nie skanuje listy wyników, całego indeksu ani archiwów i nie robi pełnego audytu przy renderowaniu. Koszt odczytu nagłówków jest O(liczba sesji) na otwarcie profilu, nie na render. W bardzo dużych bazach może to zwiększać koszt startu; nie deklarujemy pomiaru Pixela.

Dotychczasowy indeks info.lastDone nadal służy technicznemu wstępnemu odczytowi według seq; nie jest już źródłem sugestii ani etykiety ostatniego zakończonego treningu. Nie zmieniono jego formatu i nie przebudowuje się istniejących indeksów przy aktualizacji. Natywny start/finish zachowuje CAS/readback/strict complete; finish widzi odpowiednie nagłówki i snapshoty, więc wpisanie starszego treningu nie przestawia rotacji.

Usuwanie sesji przelicza kompatybilne wskaźniki po usunięciu danych, nadal w istniejącym zapisie z referencyjną kopią ratunkową. Edycja daty przelicza je przed istniejącym commit. Ręczny wybór jednostki pozostaje nietrwałym wyborem bieżącego formularza, a zakończenie treningu przywraca sugestię automatyczną. Wznowienie tej samej wersji planu wykorzystuje jej zgodną historię; nie tworzy sztucznego nowego cyklu przez sam wskaźnik aktywacji.

## Testy syntetyczne

- Node: 4 nowe testy cyklu, starszej daty, usuwania i korekty daty, tie-break seq, aktywnej sesji, własnej kolejności jednostek, izolacji wersji, przyszłych dat i ignorowania starych wskaźników. PASS.
- Istniejące 16 testów planów/importu/statystyk Node: PASS.
- Chromium: scenariusz kalendarza: późniejsza PULL A, wsteczna PUSH B, ręcznie wybrana PUSH A, aktywny typ, restart, fast/full oracle, edycja daty, usunięcie najnowszej i starszej. Pozostały trening niezmieniony. PASS.
- Chromium/PWA: aktywacja planu z innymi ID i kolejnością TEST-A/TEST-B, izolacja legacy, wsteczny wpis, restart offline i zachowanie danych. PASS.
- Natywny reader: brak getAll list historii/całego indeksu, poprawne liczniki wyników i odroczony odczyt: PASS.
- 6 regresji #160/#162 i usuwania sesji: PASS.
- 4 regresje #164/#166 (40 sesji z archiwum, przenośne odtworzenie, limit, abort i CAS): PASS.
- Składnia i service worker/hashy: PASS. Pełny końcowy CI w checks PR.

Nie wykonano migracji, resetu, testu prywatnej bazy, wdrożenia ani fizycznego odbioru Pixela 9. Matrix i #163 poza zakresem; źródłowe dane planów, backupy, konwencje i L/P bez zmiany.

## Odbiór na Pixelu 9

Po zaakceptowanym wdrożeniu i niezależnej zweryfikowanej kopii: sprawdzić sugestię według najpóźniejszego zakończonego treningu bieżącego planu; w profilu testowym dodać starszą sesję innej jednostki, zmienić jej datę na późniejszą, sprawdzić usunięcie najnowszej/starszej i punkt ratunkowy. Sprawdzić aktywny typ, wybór ręczny i restart offline. Przyszła zakończona data ma zgodnie z jawną regułą pierwszeństwo — skorygować ją świadomie w kalendarzu, jeśli była błędem użytkownika. Nie usuwać rzeczywistych treningów wyłącznie do testu.
