# Warehouse lease benchmark snapshot

This additive dataset is independent of `counties.csv`, all percentile normalization,
the four business priorities, and AI evidence. It is a fixed **Q2 2025** research
snapshot retrieved **2026-10-07**, not a live rent feed or a current-rent forecast.
The report period is deliberately visible alongside every applied benchmark.

`warehouse_leases.json` stores original source URLs and common source metadata in
`sources`; each observation references its source ID. `lease_benchmark()` combines
these into a complete provenance record. Published rates are annual USD/sq ft.
PA, NJ, NY and MD figures use the **warehouse/distribution** column, not the overall
industrial headline. OH figures are mixed industrial proxies, explicitly lower
confidence. The Cleveland MarketBeat is reproduced on pages 17–21 of a publicly
accessible Cushman & Wakefield/CRESCO offering; rent statistics are on page 18.

All admitted observations explicitly report **weighted net asking rents**.
The reports do not establish identical NNN obligations, taxes, insurance or CAM.
No assertion of exact lease equivalence is made: the model compares indicative
base rent plus the user's same occupancy assumption, with a visible instruction to
reconcile actual lease inclusions. Gross, modified-gross, monthly and unknown-basis
observations are not silently mixed into the model. No effective-rent adjustment,
lease concessions or escalation is inferred.

## Geographic rules

Mappings are explicit FIPS lists, never nearest-centroid or state-wide fallbacks.
No metro rate is labeled an observed county rent. Every applied county figure is
a **modeled estimate** using the published rate without an invented adjustment.

- Northeastern PA → Lackawanna and Luzerne only.
- Lehigh Valley → Lehigh and Northampton.
- Central PA → Cumberland, Dauphin, Lancaster and York only.
- Northern NJ → Bergen, Essex, Hudson, Morris, Passaic and Union only.
- Central NJ → Mercer, Middlesex, Monmouth and Somerset only.
- Buffalo W/D → Erie only. The report's ambiguous wider MSA description is not
  used to expand coverage to unrelated counties.
- Baltimore W/D → Anne Arundel, Baltimore County, Howard and Baltimore City only.
- Harford/Cecil W/D → the two counties share the pooled market observation.
- Cleveland overall industrial → Cuyahoga only, a low-confidence property-mix proxy.
- Lake, Medina, Portage and Stark County industrial → the named county only;
  these remain low-confidence dry-warehouse proxies because property mix differs.

Even a named county industrial submarket is not an observed rent for a specific
warehouse facility. Counties outside these conservative mappings are unavailable.
Confidence describes fitness of the estimate, not a statistical confidence interval.

## Temperature-controlled coverage

The reviewed CBRE Midwest Cold Storage Trends 2025 report discusses the sector but
does not provide usable annual lease-rate observations for these county mappings.
The reviewed general industrial reports do not distinguish refrigerated rents.
Temperature-controlled lookup therefore returns **Unavailable**, across all five
states; it never falls back to dry rent or adds a speculative percentage markup.
Verified future refrigerated observations can be added with separate warehouse
type, explicit geographic mapping and compatible lease basis.

## Cost assumptions

Indicative hourly labor = existing annual BLS pay / **2,080** (40 paid hours/week ×
52 weeks). This conversion is illustrative, not an observed hourly wage, staffing
requirement, overtime schedule or exact hourly compensation. Paid annual labor
hours and labor burden are user inputs. Annual electricity uses the existing state
commercial cents/kWh benchmark without altering it. Occupancy costs are entered
separately; users must include applicable net-lease charges and avoid double counting.

Default inputs (100,000 sq ft, 104,000 paid hours, 25% burden, 1,000,000 kWh and
$3/sq ft occupancy) are labeled illustrative, applied equally to every compared
county, and persist independently of ranking controls. They do not claim to model
typical refrigerated consumption. A missing component prevents a total/per-sq-ft
estimate; explicitly entered zero usage or occupancy is allowed, missing is not zero.
The total excludes unentered transportation, handling, inventory carrying, fit-out,
refrigeration equipment and other costs. It is not full landed distribution cost.
