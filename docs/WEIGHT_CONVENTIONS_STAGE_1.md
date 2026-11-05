# Konwencje ciężaru — etap 1

Model rozpoznaje `null` (nieokreślony), `per-implement` (jeden hantel), `barbell`, `machine-indication`, `sled`, `bodyweight-extra` oraz `combined`. Dawne `bodyweight` i pozostałe wartości zachowują dotychczasowe znaczenie; `combined` nie jest zamieniane na sztangę.

Nowy znacznik `side: "both"` w wyniku jawnie oznacza jedną serię reprezentującą obie strony. Nie jest stosowany ani wywodzony automatycznie ze starych danych. Odrębne `left`/`right` pozostają odrębnymi wynikami. Dla `per-implement` tonaż serii oznaczonej `both` uwzględnia dwa wykonania; w istniejących parach każda strona jest liczona raz. Walidacja odrzuca nakładające się `both` i L/P dla tej samej serii oraz niejednoznaczne połączenie rekordów bez przypisanej serii. Nie ustala masy ciężaru dla nieokreślonej konwencji.

`entryTotals` zwraca dla `bodyweight-extra` `tonnage: null`, `additionalLoadTonnage` i `tonnageKind: "additional-load"`. To tonaż dodatkowego obciążenia, bez masy użytkownika. Dla `sled` zwraca `tonnageKind: "recorded-load"` oraz wyłącznie tonaż wpisanego obciążenia, bez masy sanek. Podsumowanie tygodnia przenosi wartości do `additionalLoadTonnage` i `recordedSledTonnage`. Interfejs prezentujący te oznaczenia należy wdrożyć w następnym etapie.

Nie dodano interfejsu ani zapisu nowych wyników produkcyjnych; testy wykorzystują dane syntetyczne. Nie zmieniono kodu PPC1, snapshotów ani prywatnej bazy. Istniejące kopie pozostają czytelne w nowej wersji. Starsze wersje aplikacji mogą nie rozpoznać nowych wartości i wyniku `both`, dlatego nie należy deklarować zgodności nowych zapisów ze starymi wersjami. Etap 2 musi objąć edytor, pełną prezentację statystyk, porównywanie i końcowe testy PPC1 oraz odtwarzania przed produkcyjnym użyciem nowych wartości.
