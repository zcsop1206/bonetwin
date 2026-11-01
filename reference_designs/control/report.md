# Control: textbook Gibson-Ashby two-step lattice (no agent)

Deterministic output of the gateway's control_design.py (Gibson-Ashby relative density for the bone's stiffness, then strength sizing), applied at a standard lumbar cage size, exported to STL and laid out in PreForm in Rigid 10K.

- Size: 40 mm anterior-posterior (X) x 22 mm lateral (Y) x 12 mm cranial-caudal (+Z). Source: standard lumbar cage size chosen by the coordinator: 40 mm anterior-posterior (X) x 22 mm lateral (Y) x 12 mm cranial-caudal (+Z); source: Wu 2022, LLIF cage dimensions (22 mm width, 11-13 mm height); inside the judge's envelope (EVAL_SPEC G4).
- Rule design on the gateway's 20 mm block: [kb/control_design.json](kb/control_design.json) (rerun identical: True)
- The same rule over the cage envelope: [kb/control_design_sized.json](kb/control_design_sized.json) (STL rebuild identical: True)
- Gateway frame record of the rule design: [kb/gateway_frame_record.json](kb/gateway_frame_record.json)
- Material: [material_spec.json](material_spec.json)
