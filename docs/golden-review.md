# Golden fixtures - hand working

Every rupee figure in `service/tests/fixtures/itr1_cases/*.expected.json` was
worked by hand below before the golden was accepted. When a golden changes,
redo the working for that case here **in the same commit**. This file is also
the starting pack for the CA review gate - a tax professional should
independently recompute each case and sign off at the bottom.

Rates: FY 2025-26 / AY 2026-27. New regime slabs 0-4L nil, 4-8L 5%, 8-12L 10%,
12-16L 15%, ... ; std deduction 75,000; 87A rebate up to 60,000 for total
income <= 12L with marginal relief above. Old regime: 2.5L/3L(senior) nil, to 5L
5%, to 10L 20%, above 30%; std deduction 50,000; 87A up to 12,500 for TI <= 5L.
Cess 4%. Tax and payable/refund rounded to nearest 10 (s.288B).

## 01 - single employer, new regime, tax due

| Line | Working | Figure |
|---|---|---|
| Salary | 15,00,000 - std 75,000 (HRA 1,20,000 & PT 2,500 not allowed in new regime) | 14,25,000 |
| Other sources | savings 12,000 + FD 30,000 | 42,000 |
| GTI | | 14,67,000 |
| 80CCD(2) | 50,000 <= 14% x 7,00,000 = 98,000 (80C ignored) | 50,000 |
| Total income | | 14,17,000 |
| Slab tax | 20,000 + 40,000 + 15% x 2,17,000 = 32,550 | 92,550 |
| 87A | TI > 12L; excess 2,17,000 > tax, no marginal relief | 0 |
| Cess | 4% | 3,702 |
| Liability | 96,252 -> s.288B | 96,250 |
| 234B | assessed 96,250 - TDS 75,000 = 21,250 -> 21,200 x 1% x 4 months (Apr-Jul) | 848 |
| 234C | 15%: 3,100x3%=93; 45%: 9,500x3%=285; 75%: 15,900x3%=477; 100%: 21,200x1%=212 | 1,067 |
| Payable | 96,250 + 1,915 - 75,000 = 23,165 -> s.288B | 23,170 (TAX_DUE blocking) |

## 02 - old regime, HRA + home loan, refund

| Line | Working | Figure |
|---|---|---|
| Salary | 12,00,000 - HRA 1,80,000 - std 50,000 - PT 2,400 | 9,67,600 |
| House property | self-occupied interest 2,10,000 capped s.24(b) | -2,00,000 |
| Other sources | 8,000 + 20,000 | 28,000 |
| GTI | | 7,95,600 |
| VI-A | 80C 1,50,000 + 80CCD(1B) 50,000 + 80TTA min(8,000, 10,000) | 2,08,000 |
| Total income | | 5,87,600 |
| Tax | 12,500 + 20% x 87,600 = 17,520 | 30,020 |
| Cess / liability | 1,200.80 -> 31,220.80 -> s.288B | 31,220 |
| Refund | 32,000 - 31,220 | 780 |

## 03 - two employers, new regime, 87A marginal relief

| Line | Working | Figure |
|---|---|---|
| Total income | 13,00,000 - 75,000 + 9,000 | 12,34,000 |
| Slab tax | 20,000 + 40,000 + 15% x 34,000 | 65,100 |
| Marginal relief | tax capped at excess over 12L (34,000) | 31,100 (shown inside Rebate87A) |
| Cess / liability | 34,000 + 1,360 | 35,360 |
| 234B/C | assessed 35,360 - 30,000 = 5,360 < 10,000 | 0 |
| Refund | 30,000 TDS + 5,400 SA - 35,360 | 40 |

## 04 - belated (filed 20-Oct-2026), new regime

| Line | Working | Figure |
|---|---|---|
| Total income | 8,50,000 - 75,000 + 5,000 + 40,000 | 8,20,000 |
| Tax | 20,000 + 2,000 = 22,000, fully rebated u/s 87A | 0 |
| 234F | belated, TI > 5L | 5,000 |
| Balance | 5,000 - TDS 4,000 - SA 1,000 | 0 |

## 05 - senior pensioner (66), old regime

| Line | Working | Figure |
|---|---|---|
| Salary (pension) | 6,00,000 - std 50,000 | 5,50,000 |
| Other sources | 15,000 + 1,20,000 | 1,35,000 |
| VI-A | 80C 1,00,000 + 80TTB min(50,000, 1,35,000) | 1,50,000 |
| Total income | | 5,35,000 |
| Tax | senior: 5% x 2,00,000 + 20% x 35,000 | 17,000 |
| Cess / liability | | 17,680 |
| 234B/C | s.207(2): resident senior, no business income | 0 |
| Balance | 17,680 - 12,000 - 5,680 | 0 |

## 06 - revised return of 02 (filed 15-Sep-2026)

Same computation as 02. Interest/234F evaluated at the ORIGINAL filing date
(10-Jul-2026, on time) - a revised return of a timely original does not attract
234F. Refund 780. ReturnFileSec 17 with original ack no + date.

## 07 - let-out property, new regime

| Line | Working | Figure |
|---|---|---|
| Salary | 10,00,000 - 75,000 | 9,25,000 |
| House property | NAV 3,00,000 - 12,000 = 2,88,000; 30% = 86,400; interest 1,50,000 | 51,600 |
| Total income | | 9,76,600 |
| Tax | 20,000 + 10% x 1,76,600 = 17,660 -> 37,660, fully rebated | 0 |
| Refund | all TDS | 10,000 |

---

CA sign-off (name / membership no. / date / cases checked): _pending_
