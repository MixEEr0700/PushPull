# Etap 2D — konwencja wyniku i pozycja planu

Wynik może zachować konwencję snapshotu albo otrzymać inną, wybraną jawnie w edytorze. Jawny wybór jest zapisany w wyniku jako `conventionExplicit: true`; walidator sprawdza typ znacznika, poprawność konwencji, jednostkę oraz powiązanie wyniku ze snapshotem. Bez znacznika wymagania poprzedniego kontraktu nadal obowiązują. Snapshot i wcześniejsze wyniki pozostają bez zmian. Wykres porównuje tylko wyniki z tym samym kontekstem konwencji.

Przy otwarciu edytora ostatni wynik jest wybierany według ID pozycji, wersji planu i wariantu. Istniejący indeks kontekstów starszych instalacji nie przechowuje ID pozycji: jeśli jedna tożsamość występuje w kilku pozycjach, selektywny start doczytuje uwierzytelnioną listę historii tego ćwiczenia, aby wyszukać właściwe pozycje. Nie zmienia to starego indeksu ani snapshotów. Dla powtarzanej tożsamości o dużej historii koszt odczytu może wzrosnąć; nie wykonano pomiaru na fizycznym telefonie. To zgodny wstecz mechanizm odczytu, a nie migracja utrwalonego indeksu do nowej wersji.

Nowe wartości konwencji, `side: both` i znacznik jawnego wyboru wymagają wersji aplikacji obsługującej ten kod. Aktualny PPC1 zachowuje dane, ale nie potwierdzono możliwości otwarcia nowej kopii w starej aplikacji. Należy aktualizować aplikację przed jej odtworzeniem. Samo wybranie bez zatwierdzenia wyniku pozostaje szkicem; trwała sugestia następnego treningu pochodzi z ostatniego zapisanego wyniku danej pozycji.

Testy syntetyczne obejmują siedem konwencji, Maszyna → Sztanga, niezmienność wcześniejszego wyniku i snapshotu, identyczną tożsamość ćwiczenia w różnych pozycjach, restart, PPC1 oraz historyczne asymetryczne L/P. Nie wykonano testu na fizycznym Pixelu.
