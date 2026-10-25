
## Wyniki porównania

Wartości w milisekundach: **mediana / p95**, n=5. `pre72` = `4230ca3`,
`main` = `556655f`, `po` = kod PR. Pełne próbki liczbowe i spany:
[issue73-measurements.json](issue73-measurements.json).
`cold*` oznacza nowy dokument, nie zimny proces/OS telefonu;
[pełna metodologia](../ANDROID_RESPONSIVENESS_ISSUE_73.md).


### legacy-4, CPU ×4

Rozmiar live: 11352 B, wyniki: 34, snapshoty: 0; raw archiwum: 4194304 B.

| Faza | pre72 | main | po |
|---|---:|---:|---:|
| Nowy dokument (cold*) | 783 / 902 | 805 / 859 | 871 / 951 |
| Warm | 369 / 419 | 395 / 473 | 365 / 569 |
| Start offline | 372 / 386 | 340 / 357 | 358 / 412 |
| Start treningu | 209 / 255 | 205 / 222 | 193 / 240 |
| Otwarcie ćwiczenia | 73 / 75 | 74 / 91 | 75 / 97 |
| Otwarcie wyniku | 79 / 84 | 78 / 179 | 91 / 104 |
| Kg + reps + trwały szkic | 92 / 94 | 96 / 109 | 95 / 108 |
| Zapis wyniku | 163 / 210 | 179 / 190 | 208 / 244 |
| Kalendarz | 58 / 69 | 56 / 70 | 66 / 83 |

Suma blokowania długich zadań (mediana), **main → po**; maksymalne pojedyncze zadanie w pięciu próbkach w nawiasie:

| Faza | main | po |
|---|---:|---:|
| Nowy dokument (cold*) | 151 (169) | 154 (166) |
| Start treningu | 0 (58) | 0 (65) |
| Zapis wyniku | 0 (0) | 0 (54) |
| Otwarcie wyniku | 0 (130) | 0 (52) |
| Kg + reps + trwały szkic | 0 (0) | 0 (0) |

### legacy-400, CPU ×4

Rozmiar live: 617971 B, wyniki: 3400, snapshoty: 0; raw archiwum: 4194304 B.

| Faza | pre72 | main | po |
|---|---:|---:|---:|
| Nowy dokument (cold*) | 3504 / 3839 | 3291 / 3677 | 1961 / 2184 |
| Warm | 3573 / 3938 | 3383 / 3656 | 1518 / 3574 |
| Start offline | 3396 / 3702 | 3176 / 6611 | 1412 / 5821 |
| Start treningu | 5062 / 5140 | 5585 / 8595 | 3143 / 3605 |
| Otwarcie ćwiczenia | 91 / 135 | 186 / 1238 | 163 / 347 |
| Otwarcie wyniku | 109 / 111 | 106 / 121 | 120 / 164 |
| Kg + reps + trwały szkic | 94 / 109 | 94 / 108 | 94 / 114 |
| Zapis wyniku | 4615 / 5544 | 4993 / 5607 | 2897 / 3331 |
| Kalendarz | 97 / 261 | 69 / 314 | 72 / 101 |

Suma blokowania długich zadań (mediana), **main → po**; maksymalne pojedyncze zadanie w pięciu próbkach w nawiasie:

| Faza | main | po |
|---|---:|---:|
| Nowy dokument (cold*) | 2474 (2860) | 1136 (1244) |
| Start treningu | 4856 (4225) | 2368 (1221) |
| Zapis wyniku | 4261 (2888) | 2207 (1191) |
| Otwarcie wyniku | 14 (78) | 27 (80) |
| Kg + reps + trwały szkic | 0 (0) | 0 (0) |

### v2-4, CPU ×4

Rozmiar live: 552399 B, wyniki: 35, snapshoty: 4; raw archiwum: 4194304 B.

| Faza | pre72 | main | po |
|---|---:|---:|---:|
| Nowy dokument (cold*) | 6217 / 6603 | 6647 / 9681 | 3369 / 4082 |
| Warm | 5492 / 6048 | 5582 / 5994 | 3085 / 3140 |
| Start offline | 5266 / 5816 | 5580 / 9711 | 3391 / 4205 |
| Start treningu | 5698 / 6768 | 5842 / 6820 | 3019 / 4714 |
| Otwarcie ćwiczenia | 86 / 91 | 89 / 117 | 114 / 458 |
| Otwarcie wyniku | 91 / 95 | 89 / 108 | 138 / 373 |
| Kg + reps + trwały szkic | 94 / 95 | 94 / 115 | 91 / 146 |
| Zapis wyniku | 5895 / 6416 | 6144 / 7446 | 3194 / 4103 |
| Kalendarz | 58 / 69 | 60 / 130 | 57 / 82 |

Suma blokowania długich zadań (mediana), **main → po**; maksymalne pojedyncze zadanie w pięciu próbkach w nawiasie:

| Faza | main | po |
|---|---:|---:|
| Nowy dokument (cold*) | 5693 (8129) | 2589 (2672) |
| Start treningu | 5265 (4767) | 2488 (2355) |
| Zapis wyniku | 5564 (4220) | 2659 (2508) |
| Otwarcie wyniku | 2 (62) | 10 (254) |
| Kg + reps + trwały szkic | 0 (0) | 0 (0) |

### v2-40, CPU ×1

Rozmiar live: 4580644 B, wyniki: 350, snapshoty: 40; raw archiwum: 4194304 B.

| Faza | pre72 | main | po |
|---|---:|---:|---:|
| Nowy dokument (cold*) | 9516 / 11595 | 9784 / 15666 | 3604 / 4022 |
| Warm | 8958 / 13828 | 9253 / 10354 | 3304 / 5930 |
| Start offline | 8935 / 9470 | 9048 / 10549 | 3150 / 5492 |
| Start treningu | 9324 / 11309 | 9597 / 10586 | 3193 / 3578 |
| Otwarcie ćwiczenia | 47 / 61 | 44 / 207 | 44 / 66 |
| Otwarcie wyniku | 46 / 60 | 46 / 47 | 46 / 64 |
| Kg + reps + trwały szkic | 61 / 63 | 63 / 65 | 63 / 63 |
| Zapis wyniku | 9329 / 9978 | 9513 / 11259 | 3281 / 4164 |
| Kalendarz | 39 / 47 | 32 / 44 | 40 / 43 |

Suma blokowania długich zadań (mediana), **main → po**; maksymalne pojedyncze zadanie w pięciu próbkach w nawiasie:

| Faza | main | po |
|---|---:|---:|
| Nowy dokument (cold*) | 9261 (14306) | 3028 (2767) |
| Start treningu | 9051 (7670) | 2650 (1962) |
| Zapis wyniku | 8899 (8705) | 2684 (2119) |
| Otwarcie wyniku | 0 (0) | 0 (0) |
| Kg + reps + trwały szkic | 0 (0) | 0 (0) |
