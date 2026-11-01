# BoneTwin pitch citations (checked Nov 1 2026)

Every number below was seen in the named source. Nothing here is computed, so ratios such as "Ti is N times stiffer than bone" are left for you to derive and label as derived.

**How each source was read**
- **[Full]** full text opened.
- **[Abstract]** only the abstract was available or read.
- **[Secondary]** the number is reported by the named source, and I did not open the paper it cites.
- **[Vendor]** company or supplier document, not peer reviewed.

Quotes are verbatim and under 25 words. A table row is shown with `|` between cells.

## Three things to settle first

1. **The strongest pitch claim is unproven clinically.** A 2026 critical review calls periprosthetic bone loss a surrogate outcome. It says reduced stress shielding from porous implants has not been directly measured in most clinical series (C2.5). Pitch the mismatch and the bone loss, not "this prevents revisions."
2. **The anatomy needs careful wording.** The bone-loss data are for the proximal femur around a stem (Gruen zones), and total hip replacement removes the femoral head. The subsidence data describe a cage sinking into the vertebral endplates, not a replacement for a vertebral body. So the two BoneTwin targets are bone-property targets, not the sites where these clinical numbers were measured.
3. **The resin premise needs one correction.** Tough 1500 is sold as an engineering resin, but it has ISO 10993-1 skin-contact testing, and Formlabs' guide lists end-use medical devices among its uses. "Not implant-grade" is still safe to say. "Has no medical use" is not. I found no Formlabs sentence saying "not for implants" (C5.3).

---

## 1. Modulus

### C1.1 Ti-6Al-4V
- **Pitch:** Implant-grade titanium alloy has a Young's modulus of about 110 GPa, against 10–30 GPa for cortical bone.
- **Number:** 110 GPa (Ti-6Al-4V ELI, water quenched); cortical bone 10–30 GPa.
- **Reference:** Niinomi M, Liu Y, Nakai M, Liu H, Li H. Biomedical titanium alloys with Young's moduli close to that of cortical bone. *Regen Biomater* 2016;3(3):173–185. doi:10.1093/rb/rbw016, PMC4881615. [Full]
- **Quote:** Table 1: "Ti–6Al–4V ELI (WQ) | 110 |" and "Cortical bone | 10–30 |"
- **Confidence:** High for the order of magnitude. This is a review table for wrought bulk alloy, not a measurement on a finished implant, and a lattice's effective modulus is far lower (C4.2). This is the value in `figures/ti_modulus.json`.

### C1.2 Commercially pure titanium
- **Pitch:** Commercially pure titanium is about as stiff as the alloy, at roughly 103–110 GPa.
- **Number:** 110 GPa (Grade 1) or 103–107 GPa (CP-Ti). **The two sources differ.**
- **References:**
  - Oliver JN, Su Y, Lu X, Kuo PH, Du J, Zhu D. *Bioact Mater* 2019;4:261–270. doi:10.1016/j.bioactmat.2019.09.002, PMC6812334. [Full]
  - Kutluay GE, Erdoğan F, Dinçel YM. *Materials* 2026;19(18):3860. doi:10.3390/ma19183860, PMC13608771. [Full]
- **Quotes:** Oliver Table 1: "Pure Titanium (Ti) -Grade 1 | 110 |". Kutluay table: "α | CP-Ti | 103–107 |"
- **Confidence:** Medium. Both are secondary review tables, and I did not trace their primary sources. State a range.

### C1.3 PEEK
- **Pitch:** Unfilled PEEK-family polymers sit at 3–4 GPa, below cortical bone, and carbon fibre can tune them upward.
- **Number:** 3–4 GPa elastic modulus (neat polyaromatic polymers). Flexural modulus 4 GPa (unfilled), 20 GPa (30% chopped CF), 135 GPa (68% continuous CF).
- **Reference:** Kurtz SM, Devine JN. PEEK biomaterials in trauma, orthopedic, and spinal implants. *Biomaterials* 2007;28(32):4845–4869. doi:10.1016/j.biomaterials.2007.07.013, PMC2040108. [Full, first 100,000 characters of the page, plus a whole-page text search for "110 GPa"]
- **Quote:** "neat (unfilled) polyaromatic polymers can exhibit an elastic modulus ranging between 3-4 GPa"
- **Confidence:** High for neat polymer. The sentence is about the polymer class, not PEEK alone. Table 3 values are flexural, not tensile, so don't mix them with tensile numbers.

### C1.4 Cobalt-chromium
- **Pitch:** Cobalt-chromium is stiffer still, at about 210 GPa or more.
- **Number:** 210 GPa (Co-Cr-Mo); 210–253 GPa (cobalt-chromium). **The sources differ.**
- **References:**
  - Niinomi M. Development of titanium alloys for biomedical and dental applications with focusing on Young's modulus. Conference abstract, JST workshop 2013. https://www.jst.go.jp/sicp/ws2013_sas-ivf/abstract/B1_AB_Niinomi.pdf [Full, one page]
  - Oliver 2019, Table 1 (reference above). [Full]
- **Quotes:** Niinomi: "much higher Young's moduli of 180 GPa, 210 GPa, and 110 GPa, respectively" (order: 316L, Co-Cr-Mo, Ti-6Al-4V ELI). Oliver: "Cobalt–Chromium | 210–253 |"
- **Confidence:** Medium. One is a conference abstract and the other a review table. Alloy and processing are unspecified.

### C1.5 Bone reference values (reused from `targets/SOURCES.md`)
- **Pitch:** Our targets are 2,209 MPa along the main axis of the femoral head block and 714 MPa along the vertebral block's axis, computed from published fabric-elasticity data.
- **Number:** E3 = 2209 MPa (femoral head), 714 MPa (lumbar vertebra). These are BoneTwin generator outputs, not measured values from a paper.
- **References:** Simon 2025, doi:10.1016/j.bonr.2025.101884; Oefner 2022, doi:10.1007/s11517-021-02465-0; see SOURCES.md for tables and assumptions. Trabecular tissue value: Morgan EF, Unnikrisnan GU, Hussein AI. *Annu Rev Biomed Eng* 2018;20:119–143. doi:10.1146/annurev-bioeng-062117-121139, PMC6053074. [Full]
- **Quote:** Morgan: "the elastic modulus of trabecular tissue is around 10–20 GPa"
- **Confidence:** Medium. Compare like with like: apparent block moduli are not tissue moduli. SOURCES.md's femoral cortical values (17.9 and 18.16 GPa, Morgan Table 1) did not appear in the page text I extracted, probably because the table is not in the text, so those two rest on the earlier read.

### Conflicting modulus figures

| Material | Figures seen | Source |
|---|---|---|
| Ti-6Al-4V (ELI) | 110 GPa | Niinomi 2016 Table 1; Niinomi 2013; Kurtz 2007 ("titanium alloy"); Kutluay 2026 (~110) |
| Ti-6Al-4V | 101–120 GPa | Oliver 2019 Table 1 |
| Ti-6Al-4V ELI rods | 108 GPa, three-point bending | Niinomi 2016 text |
| Ti-6Al-4V ELI, ISO 5832-3 / ASTM F136 stock | 114 GPa at 20 °C | Zapp data sheet [Vendor], https://www.zapp.com/fileadmin/_documents/Datenblaetter/Werkstoffe/Medizinische%20Werkstoffe/Englisch/Implantatwerkstoffe/Ti64-3.7165-Grade-23-Grade-5-ELI-Implant-Material-Data_Sheet.pdf |
| Cortical bone | 10–30, 15–30, 7–30, 18 GPa | Niinomi 2016; Oliver 2019; Kutluay 2026; Kurtz 2007 |

**110 GPa was chosen** because it is the figure most sources agree on and it comes from a labelled table. "About 110 GPa" covers the spread for a pitch.

---

## 2. Stress shielding

### C2.1 Mechanism
- **Pitch:** When an implant is much stiffer than the bone around it, load travels through the implant, the bone is under-loaded, and it atrophies.
- **Number:** None; this is a mechanism statement.
- **Reference:** Niinomi M, Nakai M. Titanium-based biomaterials for preventing stress shielding between implant devices and bone. *Int J Biomater* 2011;2011:836587. doi:10.1155/2011/836587, PMC3132537. [Full]
- **Quote:** "the stress transfer between an implant device and a bone is not homogeneous when Young's moduli" of the two differ
- **Confidence:** High as the accepted definition. The same paper's link to loosening and refracture is a narrative statement from a materials group, not outcome data.

### C2.2 Primary modelling source
- **Pitch:** Simulations of strain-adaptive remodelling support bone loss as an adaptation to stress shielding.
- **Number:** None.
- **Reference:** Huiskes R, Weinans H, van Rietbergen B. The relationship between stress shielding and bone resorption around total hip stems and the effects of flexible materials. *Clin Orthop Relat Res* 1992;(274):124–134. https://repub.eur.nl/pub/15376/OA_1728998.pdf [Abstract section of the opened PDF]
- **Quote:** "The results sustain the hypothesis that the resorptive processes are an effect of bone adaptation to stress shielding."
- **Confidence:** Finite element simulation, not a patient study. See C2.5 for its warning about flexible stems.

### C2.3 Measured bone loss, randomised cohort
- **Pitch:** In a five-year DXA study of an uncemented titanium-alloy stem, bone density in the calcar region was still 22% lower.
- **Number:** −22% BMD, Gruen zone 7, at 5 years.
- **Reference:** Wolf O, Mattsson P, Milbrink J, Larsson S, Mallmin H. Periprosthetic bone mineral density and fixation of the uncemented CLS stem related to different weight bearing regimes. *Acta Orthop* 2010;81(3):286–291. doi:10.3109/17453674.2010.487238, PMC2876828. [Full]
- **Quote:** "Restoration toward initial BMD was observed in all zones except in zone 7 (calcar region), where BMD was reduced by 22% at 5 years."
- **Confidence:** 38 patients, mean age 54, one straight titanium stem. The randomisation was of weight-bearing regime, not stem stiffness, so this shows magnitude and not cause. Bone density in other zones recovered toward baseline.

### C2.4 Measured bone loss, other cohorts (conflicting)
- **Pitch:** Reported calcar loss ranges from about 10% to over 20% in cohorts followed for years, and one stem showed none at one year.
- **Number:** −12.60%, −11.84%, −9.56% in zone 7 across three stems (mean 4.66 years). 100% of baseline maintained in zone 7 at 1 year in another study.
- **References:**
  - Liu Y, Wei WX, Zeng Y, Ma J, Yang J, Shen B. *Orthop Surg* 2022;14(6):1059–1070. doi:10.1111/os.13265, PMC9163965. [Full, sentence search]
  - Nam D, Salih R, Barrack RL, Nunley RM. *Hip Int* 2019;29(1):51–57. doi:10.1177/1120700018761152. [Abstract]
- **Quotes:** Liu: "the most prominent BMD loss was found in Gruen zone 7 for all three stems" (values above follow in that sentence). Nam: "zone 7 (medial calcar) demonstrating 100% maintenance of the baseline BMD at 1 year"
- **Confidence:** Liu is retrospective, n=138; its measurement baseline was not checked. Nam is 31 young, active patients at one year only. **Do not present 22% as typical.** Kutluay 2026 also reports a 23% zone 7 decrease at 24 months (Alm et al.) and roughly double proximal loss with CoCr compared with titanium stems (Knutsen et al.). Both are [Secondary]; I did not open those papers.

### C2.5 The caveat that belongs in the pitch
- **Pitch:** Bone loss is well measured, but its link to implant failure is not settled, and softer stems trade it against higher interface stress.
- **Number:** None to quote as a headline. Kutluay reports 93% vs 77% 15-year survivorship, higher in hips *with* pronounced stress shielding (Engh et al., 208 hips, [Secondary]).
- **References:** Kutluay 2026 (above) [Full]; Huiskes 1992 (above).
- **Quotes:** Kutluay: "measured periprosthetic bone loss is a surrogate outcome whose link to patient-level failure has not been clearly demonstrated" Huiskes: "Flexible stems reduce stress shielding and bone resorption. However, they increase proximal interface stresses."
- **Confidence:** High that this is a live objection, and a judge from orthopaedics may raise it. Kutluay also says bone loss still matters: it was identified as an independent risk factor for periprosthetic fracture in one cohort, and it erodes bone stock for revision. That gives you an honest argument which doesn't rest on loosening.

---

## 3. Consequence and scale

### C3.1 Hip volume, registry
- **Pitch:** One national registry alone recorded 116,901 primary hip replacements in 2024.
- **Number:** 116,901 (2024), 112,076 (2023), and 1,682,998 eligible for analysis in total.
- **Population and year:** England, Wales, Northern Ireland (with the Isle of Man per NJR's scope); surgical data to Dec 31 2024.
- **Reference:** National Joint Registry. 22nd Annual Report 2025, Hips. Table 3.H2 (p. 35), section 3.H.5 (p. 126). https://reports.njrcentre.org.uk/Portals/0/PDFdownloads/NJR%2022nd%20Annual%20Report%202025_Hips.pdf [Full, searched]
- **Quote:** Table 3.H2 header: "2024 n= 116,901". Text: "50,946 (3.0%) of the 1,682,998 primary hip replacements had an associated first revision."
- **Confidence:** High. Includes all fixation types. Table 3.H2's yearly n is read from the header of a percentage table. Isle of Man coverage came from a search snippet of the 20th report's appendix, so say "England, Wales and Northern Ireland" if in doubt.

### C3.2 Hip volume, international
- **Pitch:** OECD countries average 198 hip replacements per 100,000 people.
- **Number:** 198 per 100,000 (2023 data). Earlier: 191.5 per 100,000 (2018).
- **References:**
  - OECD. Health at a Glance 2025, Hip and knee replacement. https://www.oecd.org/en/publications/health-at-a-glance-2025_8f9e3f98-en/full-report/hip-and-knee-replacement_a4d0ff34.html [Full section]
  - Jennison T, MacGregor A, Goldberg A. Hip arthroplasty practice across the OECD over the last decade. *Ann R Coll Surg Engl* 2023. https://ueaeprints.uea.ac.uk/id/eprint/94133 [Full]
- **Quote:** OECD: "The OECD averages are 198 per 100 000 population for hip replacement"
- **Confidence:** High for what it is: a mean across countries with available data, and the country range is wide. I found no verified worldwide annual count. Don't state one.

### C3.3 Hip revision rate
- **Pitch:** Most hip replacements last: about 3.6% are revised by 10 years and 8.4% by 20 years.
- **Number:** All cases 3.63% at 10 years, 5.81% at 15, 8.38% at 20. All uncemented 4.08%, 6.29%, 8.90%.
- **Reference:** NJR 22nd Annual Report, Hips, Table 3.H5, p. 50 (link above). [Full]
- **Quote:** "All cases* 1,682,998 ... 3.63 (3.59-3.66) 5.81 (5.75-5.88) 8.38 (8.23-8.53)" (10, 15 and 20-year columns; ellipsis marks skipped columns)
- **Confidence:** High. Kaplan-Meier estimates, all causes, includes metal-on-metal bearings that inflate the total. The honest framing is a low rate across a large population, not a failing therapy.

### C3.4 Aseptic loosening, registry
- **Pitch:** Aseptic loosening is the single most common recorded reason for hip revision in the UK registry.
- **Number:** 12,856 of 50,946 first revisions listed it (indications overlap). 44.7% of all single-stage revisions; 34.6% in the last five years. 1.02 per 1,000 prosthesis-years, against 4.03 for all causes.
- **Reference:** NJR 22nd Annual Report, Hips: section 3.H.5 p. 126; Table 3.H9 p. 127; Tables 3.H15(a,b) p. 149. [Full]
- **Quote:** "The most common indications for revision were aseptic loosening (12,856), dislocation / subluxation (9,111), periprosthetic fracture (8,672), infection (8,380)"
- **Confidence:** High as registry coding. Indications are not mutually exclusive. The registry doesn't attribute loosening to stress shielding, so **don't link these two without saying so.** The share is falling in recent years, and a 37% figure seen in a search snippet could not be found in the report, so don't use it.

### C3.5 Conflict: US registry says infection, not loosening
- **Pitch:** Use only if needed: the leading revision cause differs by registry and period.
- **Number:** AJRR 2023: infection 26.3%, instability 20.6%. AJRR 2019 report: instability 19.1%, aseptic loosening 17.4%, infection 13.3%.
- **References:**
  - Carender CN, Hegde V, Levine BR, Huddleston JI, Cohen-Rosenblum A. Highlights of the 2024 AJRR Annual Report. *Arthroplast Today* 2025;33:101727. doi:10.1016/j.artd.2025.101727, PMC12192333. [Full]
  - Levine BR, Springer BD, Golladay GJ. Highlights of the 2019 AJRR Annual Report. *Arthroplast Today* 2020;6(4):998–1000. doi:10.1016/j.artd.2020.09.010, PMC7772438. [Full, sentence search]
- **Quotes:** 2024: "The most common reason for revision THA in 2023 was infection (26.3%) followed by instability (20.6%)." 2019: "instability (19.1%), aseptic loosening (17.4%), other (17.1%), mechanical complications (15%), and infection (13.3%)"
- **Confidence:** **Flagged conflict with C3.4.** Coding, country and period all differ. The 2024 highlights' TKA bullet gives "mechanical loosening (24.4%)" while saying "THA" in the same sentence, so its joint is ambiguous. Don't use that figure. Full AJRR reports were not opened.

### C3.6 Lumbar fusion volume
- **Pitch:** US hospitals performed about 199,000 elective lumbar fusions in 2015, up 62% since 2004.
- **Number:** 199,140 cases in 2015, 122,679 in 2004, +62.3%.
- **Reference:** Martin BI, Mirza SK, Spina N, Spiker WR, Lawrence B, Brodke DS. Trends in lumbar fusion procedure rates and associated hospital costs for degenerative spinal diseases in the United States, 2004 to 2015. *Spine* 2019;44(5):369–376. doi:10.1097/BRS.0000000000002822, PMID 30074971. [Abstract]
- **Quote:** "Volume of elective lumbar fusion increased 62.3% ... from 122,679 cases (60.4 per 100,000) in 2004 to 199,140"
- **Confidence:** National Inpatient Sample, inpatient only, degenerative indications, and the latest year is 2015. **This counts fusions, not cages.** Not every fusion uses an interbody cage, and outpatient cases are missing. This is an administrative sample, not a registry. No spine registry figure was found.

### C3.7 Cage subsidence
- **Pitch:** Across lumbar fusion approaches, published subsidence medians run from about 13% to 27% of patients, though definitions vary widely.
- **Number:** Medians: ALIF 12.8%, LLIF with posterior fixation 13.7%, PLIF-P 15.8%, OLIF-P 17.6%, TLIF-P 21.4%, stand-alone LLIF 26.9%. Study range 0.0–51.2%.
- **Reference:** Parisien A, Wai EK, ElSayed MSA, Frei H. Subsidence of spinal fusion cages: a systematic review. *Int J Spine Surg* 2022;16(6):1103–1118. doi:10.14444/8363, PMC9807049. [Full, searched]
- **Quote:** "The subsidence occurrence median was 12.8% for ALIF, 13.7% for LLIF-P, 15.8% for PLIF-P, 17.6% for OLIF-P, 21.4% for TLIF-P, and 26.9% for LLIF."
- **Confidence:** Medium. Mixed materials, follow-up and imaging. The review says "only 2 used the same criterion (>2 mm)," and it finds "conflicting evidence on the association between subsidence and negative clinical outcomes." Revision for subsidence was 3.4% and 3% in the two studies it cites ([Secondary]). An older protocol paper gives a wider 15.9–70% (Li Q et al., *Medicine* 2021;100(49):e28085, doi:10.1097/MD.0000000000028085, PMC8663804). **These are conflicting ranges, and Parisien is the one to use.**

### C3.8 Conflict: does titanium or PEEK subside more?
- **Pitch:** Don't make a material claim here without naming the approach, since the meta-analyses disagree.
- **Number and reference:**
  - Titanium worse: OR 3.59 (95% CI 1.28–10.07), mostly cervical. Seaman S, Kerezoudis P, Bydon M, Torner JC, Hitchon PW. *J Clin Neurosci* 2017;44:23–29. doi:10.1016/j.jocn.2017.06.062. [Abstract]
  - No difference: OR 0.91 (0.54–1.52), posterior lumbar, 1,094 patients. Massaad E, Fatima N, Kiapour A, Hadzipasic M, Shankar GM, Shin JH. *Neurospine* 2020;17(1):125–135. doi:10.14245/ns.2040058.029, PMC7136087. [Full]
  - 3D-printed titanium better: OR 0.25 (0.14–0.44), lateral lumbar. Liu 2024, C4.3.
- **Quotes:** Seaman: "there is an increased rate of subsidence with titanium cage." Massaad: "There was no difference in subsidence rates between Ti and PEEK groups"
- **Confidence:** Flagged conflict. Note too that PEEK, the stiffness-matched option, doesn't reliably win. **So "lower stiffness means less subsidence" isn't supported by these data.**

---

## 4. Prior art: porous and lattice implants

### C4.1 Preclinical: fully porous stem
- **Pitch:** A fully porous 3D-printed titanium stem cut predicted stress-shielding bone loss by 75% relative to a solid stem in a laboratory and modelling study.
- **Number:** 75% reduction in bone loss, compared with a fully solid implant.
- **Reference:** Arabnejad S, Johnston B, Tanzer M, Pasini D. Fully porous 3D printed titanium femoral stem to reduce stress-shielding following total hip arthroplasty. *J Orthop Res* 2017;35(8):1774–1783. doi:10.1002/jor.23445, PMID 27664796. [Abstract]
- **Quote:** "can reduce the amount of bone loss secondary to stress shielding by 75% compared to a fully solid implant"
- **Confidence:** No patients. Finite element and in vitro work in composite femurs. The abstract doesn't state a lattice modulus. Kutluay 2026 classes this work as finite element evidence.

### C4.2 Effective modulus of porous Ti-6Al-4V
- **Pitch:** Porosity can bring Ti-6Al-4V's effective modulus down into the range of bone, from about 110 GPa to about 0.5–3 GPa in lattice regions.
- **Number:** ~0.5–3 GPa (lattice regions and specimens); bone target range 0.3–30 GPa; bulk ~110 GPa.
- **Reference:** Kutluay 2026 (C1.2). [Full]
- **Quote:** "The effective modulus reported for porous Ti-6Al-4V lattice regions/specimens (~0.5–3 GPa) descends into the bone target range (0.3–30 GPa)"
- **Confidence:** A critical narrative review from 2026, not primary tests. It warns this is "the modulus of the porous architecture itself, not the overall stiffness of the whole component."

### C4.3 Clinical: printed titanium cages
- **Pitch:** In retrospective lateral-fusion series, 3D-printed porous titanium cages subsided less often than PEEK, at 8.47% against 27.78%.
- **Number:** 8.47% vs 27.78%; OR 0.25 (95% CI 0.14–0.44); 265 patients, 441 levels.
- **Reference:** Liu SX, Zeng TH, Chen CM, He LR, Feng AP, Jhang SW, Lin GX. 3D-printed porous titanium versus polyetheretherketone cages in lateral lumbar interbody fusion: a systematic review and meta-analysis of subsidence. *Front Med* 2024;11:1389533. doi:10.3389/fmed.2024.1389533, PMC11688201. [Full]
- **Quote:** "the subsidence rate of the cage (Marchi grades I, II, and III) in the 3D-Ti group was 8.47%"
- **Confidence:** Three retrospective non-randomised studies, LLIF only. The paper doesn't measure cage stiffness, so it **doesn't show stiffness caused the difference.** See C3.8 for disagreement across approaches.

### C4.4 Optional clinical: printed porous cup
- **Pitch:** In a small randomised trial follow-up, bone density around a porous titanium cup was 12.0% higher than a porous-coated cup at ten years.
- **Number:** 3.7% higher at six years, 12.0% at ten; 51 enrolled, 38 at ten years. The earlier two-year report found no change.
- **Reference:** Axenhus M, Salemyr M, Mukka S, Magnéli M, Sköldenberg O. *Int Orthop* 2024;48(11):2835–2842. doi:10.1007/s00264-024-06289-z, PMC11490515. [Full, sentence search]
- **Quote:** "3.7% higher in the PTC group than in the PC group at six years postoperatively and 12.0% higher at ten years"
- **Confidence:** Single centre, small, with attrition, on the acetabular side. The device has a porous backside and isn't a whole-implant lattice. The comparator also differs in hydroxyapatite coating. I didn't check significance at each timepoint, so use the authors' own "potential" language.

---

## 5. Resin status

### C5.1 Rigid 10K
- **Pitch:** Rigid 10K is a glass-filled engineering resin for tooling and industrial parts. We use it as a stiff test material, not as an implant material.
- **Number:** Tensile modulus 11 GPa (current store page); 10 GPa (older V1 data sheet, Form 3, 2020). **The two differ.**
- **References:**
  - Formlabs. Rigid 10K Resin. https://formlabs.com/store/materials/rigid-10k-resin/ [Vendor]
  - Formlabs. Rigid 10K TDS, Rev 01, dated 06.09.2020 as printed, hosted by a reseller: https://core-electronics.com.au/attachments/rigid10k-TDS-ENUS-0.pdf [Vendor]
- **Quotes:** Store: "Choose Rigid 10K Resin for precise industrial parts such as molds, jigs, dies, and other tooling" TDS: "This highly glass-filled resin is the stiffest material in our engineering portfolio."
- **Confidence:** High on positioning. The store page text has no biocompatibility statement, and "Rigid 10K" doesn't appear in Formlabs' biocompatible resin guide. That is absence of a claim, not a stated prohibition. The 11 GPa in SOURCES.md matches the store page. I didn't find the current data sheet PDF.

### C5.2 Tough 1500
- **Pitch:** Tough 1500 is a polypropylene-like engineering resin, tested for skin contact and not for implantation.
- **Number:** Tensile modulus 1460 MPa post-cured (V2, Form 4); skin contact >30 days per the guide. This confirms the 1.46 GPa in SOURCES.md. The older V1 page lists 1500 MPa.
- **References:**
  - Formlabs. Tough 1500 Resin V2 TDS, Rev 05, Oct 17 2025. https://formlabs-media.formlabs.com/datasheets/25011041-TDS-ENUS-0.pdf [Vendor]
  - Formlabs. Biocompatible resins guide. https://formlabs.com/white-papers/formlabs-biocompatible-resins-a-comprehensive-guide-to-choosing/ [Vendor]
- **Quotes:** TDS: "Tough 1500 Resin has been evaluated as a skin contacting device in accordance with ISO 10993-1" Guide: "suited for applications requiring long-term skin contact (>30 days)"
- **Confidence:** High. Biocompatibility applies only with Formlabs' post-processing followed exactly, which may not match what was done to the coupons. The guide also lists "End-use medical devices and device components" and orthoses, so don't say it has no medical role.

### C5.3 What Formlabs does and doesn't say
- **Pitch:** Formlabs makes no suitability claim for medical use unless a product carries a specific indication, and these two resins have none for implants.
- **Number:** In the guide, bone contact appears only as short-term, <24 hours, and only for some BioMed resins.
- **Reference:** Formlabs Terms of Service, Medical Device Disclaimer. https://formlabs.com/terms-of-service/ [Vendor]; biocompatible resins guide (above).
- **Quotes:** Terms: "making no statement or claim as to its safety, efficacy, or suitability for a particular application including use in medical products or devices" Guide: "testing for additional contact types and durations must be conducted by the user."
- **Confidence:** This is the closest Formlabs text I found. **No Formlabs page I opened says "not for implants" in those words, or uses the word "implantable" in the guide,** so don't quote Formlabs as prohibiting it. "Cleared" is also the wrong word for these resins: the guide says "No intended uses are provided for BioMed Resins," the terms describe only certain Dental Resins as medical devices, and the guide's FDA clearance example is a customer's own system. On photopolymers for load-bearing implants generally, I found no verified source either way. Guttridge et al. 2022 (*Ann 3D Print Med*, doi:10.1016/j.stlm.2021.100044) looks relevant but returned a 403, so it isn't cited for anything.

**Suggested slide line:** "Printed in engineering resin as a stiffness-scaled test analogue. These resins are not implant materials. A match means the ratio of apparent to solid stiffness agrees in each direction." The last sentence restates the scaling in `targets/SOURCES.md`.

---

## Do not claim

1. "Stress shielding causes revisions" or "aseptic loosening is caused by stiffness mismatch." NJR codes loosening without attributing a cause, and Kutluay 2026 calls the link not clearly demonstrated.
2. "Matching bone stiffness prevents loosening or revision." No source here shows it. Huiskes 1992 warns flexible stems raise interface stresses and may increase loosening.
3. "Porous implants have been clinically proven to reduce stress shielding." Kutluay 2026 says it "has not been directly measured in most clinical series."
4. "A 75% reduction in bone loss" without "in a laboratory and modelling study." Arabnejad 2017 had no patients.
5. "Patients lose 22% of their bone." This is one zone, one stem and 38 patients, and other zones recovered. Other cohorts report about 10%, and one reports none at a year.
6. "Lower stiffness cages subside less." PEEK is closest to bone and does not consistently do better (C3.8). The 3D-Ti result comes from three retrospective LLIF studies with no stiffness measurement.
7. "Up to 70% of cages subside" or "half of cages fail." These are extremes of inconsistent definitions, and subsidence can be asymptomatic: Liu 2024 says "a certain degree of subsidence can be clinically asymptomatic." Subsidence isn't failure.
8. "199,000 cages a year." That is US inpatient elective lumbar fusions in 2015, not devices.
9. A global procedure count, or the market size. I did not verify any.
10. "Hip replacements commonly fail." NJR all-cause revision is 3.63% at 10 years.
11. "NJR aseptic loosening is 44.7% of revisions" with no qualifier. It is single-stage only, indications overlap, and the last-five-years figure is 34.6%. US data rank infection first.
12. "Our resin is biocompatible," "implant-grade," "FDA-cleared" or "ISO 10993 certified for implants." Tough 1500's testing is for skin contact, and Rigid 10K has no biocompatibility claim that I found.
13. "Formlabs prohibits implant use" or "Formlabs says these aren't cleared." It disclaims suitability instead.
14. "Our lattice is a femoral head or vertebral implant" or "a working implant." The targets are bone-property blocks, printed in a non-implant material, and the clinical data come from other sites and titanium or PEEK devices.
15. "Bone is 2.2 GPa" or "bone is 0.7 GPa" as measured facts. Those are generator outputs from SOURCES.md, resting on stated assumptions.
16. "Porous implants are stiffer after fusion, therefore worse" or the reverse. McGilvray 2018 (*Spine J* 18(7):1250–1260, doi:10.1016/j.spinee.2018.02.018, sheep, [Abstract]) reports higher *construct* stiffness with printed cages after healing, which measures fusion and not implant modulus. Don't conflate the two.

## Not verified

- ISO 5832-3 and ASTM F136 texts are paywalled and were not opened. No modulus is attributed to them. The 114 GPa is a supplier's sheet.
- No primary CP-Ti measurement was opened; only review tables.
- Martin 2019, Seaman 2017, Arabnejad 2017, Nam 2019 and McGilvray 2018 were read as abstracts only.
- Alm, Knutsen, Engh, Nemani and Malham figures are reported through Kutluay or Parisien.
- The current Rigid 10K V1.1 data sheet PDF was not located.
- Isle of Man coverage of the NJR 22nd report.
- Jennison 2023's journal name and year come from a search summary; the opened PDF was the repository copy.
