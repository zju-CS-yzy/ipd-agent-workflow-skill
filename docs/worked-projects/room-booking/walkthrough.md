# First-use walkthrough: findings and revisions

[Worked project index](index.md) · [中文](walkthrough.zh-CN.md)

The author actually completed a 3IR/6SR/12AR project following stage draft 0.2.0, then separately checked traceability and executed code. This was not an independent human usability study or blind Agent trial. Three findings informed stage draft 0.2.1 and register 1.1.1 in pack 1.2.1, retaining the original 1.2.0 pack. All sixteen final documents were revalidated against the revised templates.

| Location / issue | Break encountered while filling | Added guidance | Check in this project |
| --- | --- | --- | --- |
| Derivation references | Repeated generic subsection titles cannot uniquely locate one derivation from a register | Give every record a unique ID and include its candidate/exact requirement reference in the heading | Six D-SR and twelve D-AR anchors, with corresponding SR/AR register links |
| Front-matter scope | No SRs exist when TR2 starts and no ARs when TR3 starts, yet metadata can appear to require them in advance | Begin with known inputs, then add registered children to describe the stage-completion snapshot | TR1 has 3IR; TR2 3IR+6SR; TR3 6SR+12AR; TR4 all 21 |
| Later register updates | Linking TR3 to a table later overwritten by TR4 leaks implementation/passes into the earlier stage | Preserve stage snapshots or immutable revisions; mark missing fields with not formed/not run, owner and planned stage | IR-TR1 has no SR versions, SR-TR2 no AR versions, AR-TR3 no actual results; AR-TR4 separately references E1 |

## Chapter walkthrough

- TR1 starts with raw input, develops individual IRs in chapter 4, checks feasibility in chapter 5 and consolidates in chapter 6, without depending on SRs.
- TR2 scenarios supply premises, chapter 3 derives each SR with quantitative or logical support, and chapter 4 consolidates. Module allocation does not presume ARs.
- TR3 architecture first references SRs. Chapter 5 develops individual ARs from SRs and design, then checks complete child combinations. The 3→6→12 count is a case result, not a universal fixed ratio.
- TR4 maps every AR to detailed design and source functions. AR, SR and IR scenarios execute separately instead of inferring parent outcomes from child pass flags. Independent expectations distinguish 120 occupied minutes from a 150-minute span.
- Registers use rowspan for genuinely common context or parents, never identities or criteria. Requirement, document, template and source versions remain distinct.

## Retained limits

The static educational catalog is not another canonical project database. Real projects still require canonical registration and authorized acceptance. The example does not simulate six-phase governance or fabricate human approval. E1 IR cases are software scenario evidence; actual user validation remains unperformed. Twenty-one cases establish neither production readiness nor domain-wide requirement sufficiency.

Within this bounded case, no dangling parents, missing rationale links, unknown variables or early-stage exposure to later results remain. Domain sufficiency, real usability, concurrency and persistence need other cases. This does not establish that every first-time user will encounter no problems.
