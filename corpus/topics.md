# Topic candidates, wave-consensus corpus

Window: 2026-08-14 to 2026-08-25. Guaranteed post-cutoff for all six panel
models (27B verified blind by probe, 2026-08-25, see cutoff-probe/probes.md;
4B cutoffs are placeholders until those models are served and probed, tasks
11-12).

Source: Wikipedia Portal:Current events, August 2026 (fetched 2026-08-25),
plus earlier tavily verification. Every entry lists its primary source URL(s)
as found in the portal. This file is the CANDIDATE pool: 36 candidates, target
corpus is 30. Selection is flagged per row; drops are tentative pending
co-designer sign-off.

Rules for a qualifying topic:
- The event post-dates 2026-08-14 (or started inside the window with a dated,
  self-contained beat inside it).
- Carries at least 3-4 independently verifiable sub-facts (names, numbers,
  dates, places, organisations) so it can seed 40 propositions.
- Real-world facts will be re-verified one by one in the fact-check pass
  (task 4); the text is the oracle.
- Verbatim: use a real article verbatim where one exists (source URL recorded
  in the manifest); otherwise draft from these verified facts.

Status: CANDIDATES, not frozen. Frozen at Phase 0 (task 10).

## Existing candidates (T01-T12)

| id   | date       | topic                                                        | key verifiable facts (verify in task 4)                                                        | primary source(s) |
|------|------------|--------------------------------------------------------------|--------------------------------------------------------------------------------------------------|-------------------|
| T01  | 08-15      | M7.7 Flores earthquake, Indonesia (VERBATIM x3)              | Mw 7.7, 15 Aug 05:58 WITA, East Nusa Tenggara, toll 47 (initial) to 73 (late Aug), 1,182 injured, tsunami 1.61 m | AP, Reuters, Al Jazeera, CBS, Wikipedia |
| T02  | 08-15      | Hurricane Lala, Hawaii (VERBATIM x1)                         | Category 1, passed south of Big Island 15 Aug 13:45 HST, downgraded to TS 16 Aug, 130,000+ outages (~70% of Big Island), 2-3 ft rain <24 h, at least 1 killed, 90-yr-old woman in Naalehu, super-El-Nino link | NASA Earth Observatory, CNN, NHC, AP |
| T03  | 08-14..21  | USS Abraham Lincoln record deployment (VERBATIM x2)          | left San Diego 21 Nov 2025, only port call Guam 11-12 Dec 2025, 272 consecutive days at sea (record), relieved by USS George Washington (arrived ~20 Aug), 9-month deployment, mental-health and supply reports, return in 3-4 weeks | ABC10, Center Square, migflug.com, AP, Guardian |
| T04  | 08-22..23  | Hawk Fire, Reno, Nevada                                      | began 22 Aug, human-caused (PBS), >10,500 acres by 22 Aug (CGTN), >20 sq mi / 53 sq km by 23 Aug, spread over Peavine Peak, Humboldt-Toiyabe National Forest, tens of thousands evacuated, state of emergency for Washoe County (Gov. Lombardo) | PBS, Reuters, CGTN |
| T05  | 08-18/19   | US national debt tops $40 trillion                           | first crossing (announced 19 Aug, crossed 18 Aug), $40.047T, Treasury report, "doubled under Trump, Biden" framing | Reuters, CNBC, AP |
| T06  | ~08-14     | White House ballroom SCOTUS filing                           | motion filed ~14-15 Aug, Supreme Court, ballroom legality (verify case name, party, exact date) | earlier tavily pass (needs re-verification) |
| T07  | ~08-21     | Prince Harry and Meghan return to UK                         | first return since (verify), duration, purpose (verify) | earlier tavily pass (needs re-verification) |
| T08  | ~08-18     | Mike Lindell, Minnesota gubernatorial primary recount        | Lindell v. (verify opponent), MN AG (verify name), margin (verify), 18 Aug date | earlier tavily pass (needs re-verification) |
| T09  | 08-17      | Jason Arday vigil, London                                    | Arday died 14 Aug (portal recent deaths), vigil 17 Aug, location (verify: verify exact venue) | Wikipedia recent deaths, earlier tavily pass |
| T10  | 08-15      | Indiana floods                                               | six dead from storm floods, 15 Aug report, counties (verify) | Reuters |
| T11  | ~08-15     | Israel, West Bank settlement plan                            | plan details (verify: number of units, dates, authority) | earlier tavily pass (needs re-verification) |
| T12  | 08-19/21/24| US "economic war" / Operation Economic Outcast vs Iran       | Trump announces economic war + sanctions on trading countries (19 Aug); Bessent launches "Operation Economic Outcast" (24 Aug, WSJ/Politico); "greatest coordinated economic isolation in history" quote (Democracy Now, 21 Aug - DATE CONFLICT, verify which day what); rial hits 2.02M/USD record low (24 Aug) | The Hill, WSJ, Politico, Time, Democracy Now |

## New candidates (T13-T36), 24 collected 2026-08-25

| id   | date       | topic                                                        | key verifiable facts (verify in task 4)                                                        | primary source(s) |
|------|------------|--------------------------------------------------------------|--------------------------------------------------------------------------------------------------|-------------------|
| T13  | 08-15/16   | Lake Kariba vessel capsizing, Zimbabwe                       | capsizing "last week" (before 15 Aug), toll rises to 72 (26 bodies 15 Aug, 12 more 16 Aug), children among dead | AP, CNN |
| T14  | 08-17      | Tupac Shakur murder trial begins, Las Vegas                  | trial opens 17 Aug, defendant Duane "Keffe D" Davis, murder 1996 (verify exact date/place: Las Vegas), alleged role (shooter's identity per earlier reporting) | BBC, CNN |
| T15  | 08-16      | Somali Airlines resumes after 35-year pause                  | announced 16 Aug, resumes mid-September (verify exact date), 35-year pause since 1991 civil war, first flights (verify routes) | Bloomberg, Dawan Africa |
| T16  | 08-17/18   | Discord suspends live streaming in Brazil                    | order from Brazilian data-protection authority (ANPD, verify), trigger: death of 13-year-old allegedly encouraged during broadcast, suspended features: live streaming, screen sharing, video calls | RFI (AFP) |
| T17  | 08-21      | TikTok, $400M COPPA settlement with US DOJ                   | $400 million, Justice Department suit, children under 13, parental-consent violation, settlement date | France 24 (AFP) |
| T18  | 08-22      | Humanoid robot 100 m record, Beijing                         | World Humanoid Robot Games, Beijing, 100 m in 9.39 s, beats Bolt's 9.58 s (2009, Berlin), robot name (NBC URL says "Lightning" - verify) | NBC News |
| T19  | 08-21      | The Odyssey (2026), highest-grossing R-rated film            | $1.35B worldwide, surpasses Deadpool & Wolverine, R-rated record, director (verify: Nolan), studio (verify) | The Guardian |
| T20  | 08-21      | JDT 109-match unbeaten run, world record                     | Johor Darul Ta'zim, Malaysia Super League, 109 matches, beat Kuching City 3-0 on 21 Aug, world record for top-flight league | RFI (AFP) |
| T21  | 08-22/25   | US 50% tariffs on Canada, retaliation                        | talks failed, 50% on ~US$20B of Canadian goods (22 Aug), PM Mark Carney announces equivalent retaliation (22 Aug), Canada lists ~US$20B of US imports (25 Aug) | AFP, Reuters |
| T22  | 08-20      | Bangladesh, first contested presidential election in 35 years| Mirza Fakhrul Islam Alamgir elected by Jatiya Sangsad, 20 Aug, takes office 21 Aug, first contested in 35 years, ruling-party veteran | Al Jazeera, AP, Dhaka Tribune |
| T23  | 08-20      | Evergrande founder Hui Ka Yan, life sentence                 | life imprisonment, fraud/bribery/embezzlement, CNY 15.8B (US$2.35B) combined fines on Evergrande + real estate arm, court (verify which) | CNA (AFP) |
| T24  | 08-19      | Mount Ololokwe helicopter crash, Kenya                       | 6 passengers + pilot killed, includes Ecuadorian intelligence head Michele Sensi-Contugi and his wife, 4 Americans (NBC URL - verify), Samburu County, Mount Ololokwe | NBC News, AP |
| T25  | 08-18/22   | Gold mine collapse, Central African Republic                 | at least 100 killed, Baboua, on Cameroon border, government closes mine 22 Aug for non-compliance | RTE, AP |
| T26  | 08-24      | Gang raid near Port-au-Prince, Haiti                         | at least 47 killed, 22 injured, overnight, outskirts of Port-au-Prince | Reuters |
| T27  | 08-24      | US removes Syria from state-sponsors-of-terrorism list       | formal removal, 24 Aug, first removal since (verify), conditions (verify) | Straits Times, Jerusalem Post |
| T28  | 08-19      | Merck-Moderna melanoma vaccine, late-stage results           | positive late-stage trial, prevents melanoma recurrence, including high-risk patients, companies: Merck + Moderna | France 24 (AFP), CNBC |
| T29  | 08-17/20   | DRC Ebola outbreak, deadliest in country's history           | UN: at least 2,325 dead (17 Aug), WHO: 70,000 doses of Merck vaccine candidate to DRC (20 Aug), 2026 epidemic (ongoing) | DW, CNBC Africa |
| T30  | 08-14      | Venezuela releases 131 detainees                             | 131 under alternative custody, national reconciliation program, post-Maduro removal, Foro Penal: at least 45 political prisoners | RFI (AFP) |
| T31  | 08-15      | Liechtenstein moves to absolute primogeniture                | Hereditary Prince Alois announces, any future descendant of him and Sophie inherits regardless of sex, first women can inherit | AP |
| T32  | 08-14      | France blocks under-15 social media ban                      | Constitutional Council blocks bill, ban on social media for under-15s, Macron orders PM Sebastien Lecornu to re-work and resubmit | RFI, Business of Fashion |
| T33  | 08-15      | 180-foot Our Lady of Mercy statue, Konotopie, Poland         | 180 ft / 55 m, tallest of its kind in Europe, dedicated to Virgin Mary, inaugurated in Konotopie, blessed (Vatican News) | NBC News, Vatican News |
| T34  | 08-15/16   | Four Antonello da Messina works stolen, Messina museum       | 4 paintings, Renaissance artist, Regional Museum of Messina, Sicily, stolen over holiday (Guardian says holiday) | The Guardian, Reuters |
| T35  | 08-16      | Ukraine's 822-drone attack, largest of the year              | 822 drones, over 600 toward Moscow, at least 7 killed, 39 injured, Wildberries warehouse destroyed, Russian officials: largest this year | BBC |
| T36  | 08-21      | Panama Canal limits transits over El Nino drought            | limit on number of ships for next month, El Nino causing regional droughts, announced 21 Aug | DW |

## Reserve (not in the 36; use if a selection drops)

T37 California first-in-US tire efficiency standards (08-17, NYT: 2029 target, 70% of options gone by 2033).
T38 Security Aviation Flight 45, Cessna 441, Cape Newenham radar site, Alaska, 8 killed (08-20, AP).
T39 MV Ocean Winner, Panama-flagged, sinks off Odisha, 2 rescued 22 missing (08-22/23, Reuters, Times of India).
T40 Japan, first execution under Takaichi, 58-year-old for 2009 Osaka pachinko arson, 5 killed (08-21, Japan Times).
T41 Turkey issues Interpol warrant for Netanyahu over Gaza flotilla, justice minister Akın Gürlek (08-21, Reuters).
T42 Hong Kong convicts Lee Cheuk-yan and Chow Hang-tung, incitement to subversion, Tiananmen vigils, up to 10 years (08-21, RFI).
T43 Mexican Navy seizes 3.2M doses cocaine off Michoacan, MX$340.2M / US$20.11M (08-17, Lopez Doriga).
T44 Kazakhstan Kurultai election, first convocation, new constitution 15 Mar, Adilet 71% (08-23/24, Reuters).
T45 IndyCar Freedom 250, National Mall, DC, 250th anniversary, Kyle Kirkwood wins; Jeff Gordon wins IROC (08-22/23, NYT Athletic).
T46 Enes Kanter Freedom ejected from WNBA Sky-Fever game at Wintrust Arena, 2027 draft declaration (08-23, AP).
T47 Syria grand mufti Ahmad Badreddin Hassoun, life for war crimes under Assad (08-24, AP, Al Jazeera).
T48 US strikes alleged drug vessel in Pacific, Operation Southern Spear, 2 killed, first in two months (08-24, PBS, CNN).
T49 Spanish F/A-18 shoots down Russian drone over Romania near Galati (08-16, Politico).
T50 Fagersta school sword stabbing, Sweden, 1 killed 3 injured (08-21, Reuters).
T51 Kryvyi Rih shopping-center drone strike, 16 killed 130+ injured (08-21, Reuters).
T52 Mw 5.9 Ibaraki, Japan, 45 injured (08-23, Nikkei).
T53 Philippines, 23 killed by monsoon + Tropical Storm Kujira (08-17, Anadolu).
T54 Conakry landfill collapse, Guinea, at least 30 killed (08-23, BBC).
T55 Billings, Montana, 8 killed in domestic shooting + house fire (08-23, People).
T56 Graeme Dott found guilty of child sex abuse (08-24, Guardian).

## Tentative selection (30 of 36) - pending co-designer sign-off

Drop 6 (weakest fact density / least self-contained / unverified):
- T06 ballroom SCOTUS filing (unverified, needs case details)
- T07 Harry and Meghan return (unverified)
- T09 Jason Arday vigil (thin, single event)
- T11 West Bank settlement plan (unverified)
- T31 Liechtenstein primogeniture (niche, single fact)
- T33 Konotopie statue (single fact)

Keep 30: T01, T02, T03, T04, T05, T08, T10, T12, T13, T14, T15, T16, T17,
T18, T19, T20, T21, T22, T23, T24, T25, T26, T27, T28, T29, T30, T32, T34,
T35, T36.

Still to verify inside the keep-30 (task 4 fact-check pass): T08 (Lindell
recount details), T12 (Operation Economic Outcast - resolve the 21 Aug vs
24 Aug date conflict). The dropped set is not dead: T06/T07/T09/T11 are
re-verifiable - if task 4 confirms them they displace the weakest kept entry,
not the strong core. T31/T33 are dropped on fact density.

Domain spread of the keep-30: disasters (T01, T02, T04, T13, T24, T25, T26),
politics (T08, T12, T21, T22, T27, T30, T32), business (T03, T05, T15, T17,
T23), science/health (T18, T28, T29), sports/film (T14, T19, T20), tech (T16),
military (T35), arts (T34), economics/infra (T36).

Open items before freeze:
- Re-verify T06, T07, T08, T09, T11 (earlier tavily pass, pre-window-mapping).
- Resolve T12 date conflict (21 Aug Democracy Now vs 24 Aug WSJ/Politico).
- Per-family cutoff dates: 27B probed; 4B families unfixed (task 9) - their
  cutoffs are placeholders until served (task 11).
