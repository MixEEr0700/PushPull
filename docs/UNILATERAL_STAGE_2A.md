# Etap 2A — zapis uproszczonych serii

Nowy formularz ćwiczenia z wymaganymi stronami tworzy jeden rekord `side: "both"` na serię. Usuwanie wszystkich serii i ich ponowne dodanie zachowuje ten sposób wykonania w stanie szkicu. Dropsety pozostają segmentami rodzica i korzystają z istniejącego `dropOrigin`. Nie powstają równolegle rekordy L/R.

Edytowanie istniejącego wyniku korzysta z jego zapisanych rekordów, bez spłaszczania. Przy kopiowaniu poprzedniego wyniku do nowego formularza tylko kompletna, jednoznaczna i symetryczna para `per-implement` może być reprezentowana przez nowy rekord `both`. Źródłowy wynik i identyfikatory jego rekordów nie są modyfikowane. Asymetryczne, niekompletne lub nieporównywalne dane zachowują wcześniejszą obsługę szczegółów i blokadę niekompletnej pary.

Tonaż nowego wyniku `per-implement` uwzględnia obie strony jeden raz. Historyczne L/R są nadal sumowane jeden raz na każdy zapis strony. Panel statystyk korzysta z `entryTotals`, a edytor z `performanceTonnage`; nieokreślona konwencja nie daje zgadywanego tonażu.

Test przeglądarkowy `test_both_production_2a` wykonuje istniejący import i aktywację zatwierdzonego planu na syntetycznej bazie, następnie wpisanie wartości, dodanie/usunięcie i ponowne dodanie serii oraz dropsetu, zapis, restart i odczyt tych samych rekordów. Potwierdza trzy rekordy `both`, cztery segmenty i tonaż 1280 kg dla 20 kg × 8 powtórzeń. Drugi przypadek zachowuje asymetryczne L/R i weryfikuje zmianę tylko jednej strony. Testy wcześniejszej historii otrzymują jawne dane historyczne zamiast konstruować je przez nowy formularz.

Nie dodano siedmiu opcji interfejsu, zapamiętywania konwencji na pozycji ani znaczników sprzętu. Nie wykonano operacji na prywatnych danych ani fizycznym Pixelu. Pełny odbiór Androida i zgodność nowych kopii ze starszą aplikacją nie są potwierdzone w tym etapie. Starsza aplikacja może odrzucić nowy znacznik `both`; wymagane jest używanie zaktualizowanej wersji do jego odczytu.
