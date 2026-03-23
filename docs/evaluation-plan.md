# Evaluation plan for self-hosted medical EHR parsing and de-identification

## Objective
Use this workspace to evaluate self-hosted open source document parsers and OCR systems as step 1 toward a medical record de-identification pipeline, then evaluate de-identification options as step 2.

## Scope
### Step 1: parsing and OCR
Assess how well each system extracts:
- plain text
- reading order
- word and line bounding boxes
- tables and table structure
- forms and key-value regions
- embedded image text
- difficult scan content such as low-resolution faxes and handwriting

Candidates:
- OLMOCR
- Marker (Surya OCR)
- MonkeyOCR
- PaddleOCR (PP-StructureV3)
- MinerU

### Step 2: de-identification
Assess text and image redaction quality using step 1 outputs and original page images.

Candidates:
- `philter`
- `presidio image redactor`

## Success criteria
A successful step 1 candidate should:
- run fully self-hosted on local hardware
- extract clinically useful text with stable reading order
- preserve location information needed for redaction
- detect tables and form structure with acceptable fidelity
- tolerate degraded scans better than generic OCR baselines
- be reproducible and operationally maintainable

A successful step 2 candidate should:
- detect PHI with high recall on clinical text
- support or enable precise image redaction regions
- minimize visible PHI leakage in final documents
- keep false positives manageable for downstream usability

## Evaluation corpus design
Create a balanced local corpus with at least 5-10 samples per bucket:

1. Native digital PDFs
   - discharge summaries
   - lab reports
   - referral letters
2. Scanned PDFs
   - clean scans
   - skewed scans
   - noisy low-resolution faxes
3. Layout-heavy records
   - forms
   - insurance paperwork
   - tables and flowsheets
4. Visual complexity
   - pages with graphs
   - diagrams
   - stamps
   - signatures
5. Handwriting
   - physician notes
   - annotations on printed records
6. Mixed-content packets
   - multi-page records combining the above

For each document, capture metadata in the inventory:
- sample ID
- source type
- page count
- content class
- scan quality
- handwriting present yes/no
- tables present yes/no
- diagrams present yes/no
- PHI density low/medium/high
- notes on expected extraction difficulty

## Ground truth strategy
Use a tiered ground truth approach.

### Tier A: full annotation for a smaller gold set
For the hardest and most representative subset, create:
- reference plain text
- reference page reading order
- labeled table regions
- labeled key PHI spans for step 2
- page image boxes for visible PHI where feasible

### Tier B: targeted annotation for wider coverage
For a broader set, annotate only:
- critical text spans
- important tables
- selected PHI spans
- obvious parser failures

This keeps effort manageable while still enabling robust comparison.

## Step 1 evaluation dimensions
Score each parser across these dimensions.

### 1. OCR and text fidelity
Measure:
- character error rate
- word error rate
- medical term preservation
- numeric fidelity for dates, IDs, lab values, dosages

Notes:
- Clinical parsing is especially sensitive to small digit and punctuation errors.
- Track errors separately for body text, headers, and small-print footers.

### 2. Reading order and layout fidelity
Measure:
- paragraph sequencing accuracy
- multi-column handling
- header/footer contamination
- section boundary preservation

### 3. Box and region extraction
Measure:
- word/line box availability
- coordinate consistency
- region granularity
- recoverability of source page positions for redaction

### 4. Table extraction
Measure:
- table detection recall
- row/column reconstruction quality
- merged-cell handling
- preservation of lab-result associations

### 5. Robustness on difficult inputs
Measure separately for:
- low-resolution faxes
- skewed or rotated scans
- stamps and overlapping marks
- handwriting
- mixed image/text pages

### 6. Operational fit
Measure:
- installation complexity
- hardware requirements
- runtime per page
- peak memory use
- batch processing support
- output formats
- licensing and maintenance activity

## Step 1 scoring rubric
Use a 1-5 scale per category, plus raw metrics where available.

Suggested weighted score:
- OCR and text fidelity: 30%
- reading order and layout fidelity: 15%
- box and region extraction: 15%
- table extraction: 15%
- difficult-input robustness: 15%
- operational fit: 10%

Add hard gates:
- must be self-hostable
- must expose enough location detail for downstream redaction
- must not catastrophically fail on noisy medical scans

## Step 1 evaluation workflow
1. Create sample inventory in [samples/manifests/sample-inventory.template.csv](../samples/manifests/sample-inventory.template.csv).
2. Freeze a first-pass corpus version.
3. Run each parser on the identical corpus.
4. Save raw outputs in parser-specific subfolders under [evaluations/step1-parsers](../evaluations/step1-parsers).
5. Normalize outputs into a common comparison schema:
   - document ID
   - page number
   - text blocks
   - lines
   - words
   - coordinates
   - tables
   - images or regions
6. Score against the gold set and targeted annotations.
7. Summarize results in [evaluations/step1-parsers/scorecard-template.csv](../evaluations/step1-parsers/scorecard-template.csv).
8. Shortlist the top 1-2 tools for step 2 integration.

## Step 2 evaluation dimensions
### A. Text PHI detection using `philter`
Measure:
- recall on names, dates, addresses, phone numbers, MRNs, account numbers, provider names, organizations
- precision to estimate over-redaction
- support for clinical note conventions and abbreviations
- ease of adding custom rules or lexicons

### B. Image redaction using `presidio image redactor`
Measure:
- correctness of redaction boxes on page images
- dependence on upstream OCR quality
- leakage rate for visible PHI
- preservation of non-PHI content readability

### C. End-to-end de-identification quality
Measure:
- page-level PHI leakage count
- document-level recall of PHI removal
- usability of the redacted output
- auditability of what was removed and why

## Step 2 workflow
1. Feed shortlisted step 1 outputs into `philter` for text-level PHI detection.
2. Test image redaction paths using original page images plus OCR boxes.
3. Compare pure text de-identification versus image-aware redaction.
4. Review false negatives first; PHI leakage is the highest-risk failure class.
5. Produce a final recommendation for the combined pipeline.

## Key risks and mitigations
### Risk: handwriting is poorly recognized
Mitigation:
- score handwriting separately
- consider manual review fallback for handwritten pages

### Risk: parser output lacks usable coordinates
Mitigation:
- treat as a hard limitation for image redaction use cases

### Risk: table extraction breaks clinical meaning
Mitigation:
- separately validate lab panels, flowsheets, and medication tables

### Risk: false sense of safety from text-only de-identification
Mitigation:
- always inspect rendered page images for residual PHI

### Risk: sample bias
Mitigation:
- maintain balanced coverage across document types and difficulty levels

## Deliverables
### Phase 1 deliverables
- corpus inventory
- parser run logs
- normalized outputs
- step 1 scorecard
- shortlist recommendation

### Phase 2 deliverables
- PHI gold annotations for selected set
- de-identification scorecard
- final pipeline recommendation
- documented limitations and fallback procedures

## Immediate next actions
1. Populate the sample inventory template.
2. Define the first gold set of 20-30 representative pages.
3. Decide the common normalized output schema for parser comparison.
4. Add runner scripts for each step 1 tool.
5. Add scoring scripts for OCR, layout, tables, and PHI leakage.
