"""Master data for the demo company: a mid-sized Indian pump and gearbox manufacturer.

Every name here is fictional. Rates are in INR and are the base purchase price before
supplier-specific pricing and drift are applied by the generator.
"""

COMPANY = {
	"company_name": "Apex Precision Engineering Pvt Ltd",
	"abbr": "APE",
	"country": "India",
	"currency": "INR",
	"timezone": "Asia/Kolkata",
	"state": "Maharashtra",
	"city": "Pune",
	"domain": "apexeng.example",
}

# (group, parent group)
ITEM_GROUPS = [
	("Raw Material", "All Item Groups"),
	("Steel", "Raw Material"),
	("Non-Ferrous Metals", "Raw Material"),
	("Castings", "Raw Material"),
	("Polymers & Rubber", "Raw Material"),
	("Components", "All Item Groups"),
	("Bearings", "Components"),
	("Fasteners", "Components"),
	("Seals & O-Rings", "Components"),
	("Electrical", "Components"),
	("Hydraulics & Pneumatics", "Components"),
	("Consumable", "All Item Groups"),
	("MRO Spares", "All Item Groups"),
	("Packaging", "All Item Groups"),
	("IT Equipment", "All Item Groups"),
	("Office Supplies", "All Item Groups"),
	("Services", "All Item Groups"),
	("Finished Goods", "All Item Groups"),
]

# Item tuples: (code, name, group, uom, base_rate, lead_days)
# Purchased stock items get reorder levels; services are non-stock.


def _items():
	items = []

	def add(code, name, group, uom, rate, lead):
		items.append({"code": code, "name": name, "group": group, "uom": uom, "rate": rate, "lead": lead})

	for t in ("1.6", "2", "3", "5"):
		add(f"RM-MSS-{t.replace('.', '')}", f"MS Sheet {t}mm 1250x2500", "Steel", "Kg", 72, 7)
	for d in (20, 32, 50, 75):
		add(f"RM-EN8-{d}", f"MS Round Bar EN8 {d}mm", "Steel", "Kg", 79, 7)
	for t in ("1", "2", "3"):
		add(f"RM-SS304-{t}", f"SS304 Sheet {t}mm", "Steel", "Kg", 248, 10)
	for d in (25, 40):
		add(f"RM-SS316-{d}", f"SS316 Round Bar {d}mm", "Steel", "Kg", 385, 12)
	add("RM-AL-LM6", "Aluminium Ingot LM6", "Non-Ferrous Metals", "Kg", 236, 10)
	for d in (25, 50):
		add(f"RM-AL6061-{d}", f"Aluminium Bar 6061 {d}mm", "Non-Ferrous Metals", "Kg", 312, 10)
	for d in ("05", "10"):
		add(f"RM-CUW-{d}", f"Enamelled Copper Wire {d[0]}.{d[1]}mm", "Non-Ferrous Metals", "Kg", 890, 14)
	for d in (12, 20):
		add(f"RM-BR-{d}", f"Brass Rod {d}mm", "Non-Ferrous Metals", "Kg", 560, 10)
	add("RM-CI-PB10", "CI Casting Pump Body HGP-10 (rough)", "Castings", "Nos", 1450, 21)
	add("RM-CI-PB20", "CI Casting Pump Body HGP-20 (rough)", "Castings", "Nos", 2150, 21)
	add("RM-CI-PB40", "CI Casting Pump Body HGP-40 (rough)", "Castings", "Nos", 3300, 21)
	add("RM-CI-CP", "CI Casting Volute Casing CP series (rough)", "Castings", "Nos", 2600, 21)
	add("RM-CI-GB", "CI Casting Gearbox Housing (rough)", "Castings", "Nos", 4100, 25)
	add("RM-AL-IMP", "Aluminium Impeller Casting (rough)", "Castings", "Nos", 980, 18)
	add("RM-NY66-50", "Nylon 66 Rod 50mm", "Polymers & Rubber", "Kg", 420, 7)
	add("RM-PTFE-3", "PTFE Sheet 3mm", "Polymers & Rubber", "Kg", 950, 10)
	add("RM-NBR-3", "NBR Rubber Sheet 3mm", "Polymers & Rubber", "Kg", 210, 7)

	for n, rate in (("6201", 95), ("6202", 110), ("6203", 125), ("6204", 150), ("6205", 175),
			("6206", 230), ("6207", 300), ("6208", 380), ("6209", 460), ("6210", 540)):
		add(f"BRG-{n}", f"Deep Groove Ball Bearing {n}-2RS", "Bearings", "Nos", rate, 7)
	for n, rate in (("30205", 420), ("30206", 510), ("32210", 980)):
		add(f"BRG-{n}", f"Taper Roller Bearing {n}", "Bearings", "Nos", rate, 10)

	for m, base in ((6, 140), (8, 230), (10, 360), (12, 520), (16, 950)):
		for length in (25, 40, 60):
			add(f"FST-HB-M{m}x{length}", f"Hex Bolt M{m}x{length} HT 8.8 (box of 100)", "Fasteners", "Box",
				round(base * (1 + (length - 25) / 70)), 5)
	for m, rate in ((6, 60), (8, 95), (10, 150), (12, 230), (16, 420)):
		add(f"FST-HN-M{m}", f"Hex Nut M{m} (box of 100)", "Fasteners", "Box", rate, 5)
	for m, rate in ((6, 35), (8, 55), (10, 80), (12, 120)):
		add(f"FST-SW-M{m}", f"Spring Washer M{m} (box of 100)", "Fasteners", "Box", rate, 5)
	for m, rate in ((6, 260), (8, 410), (10, 640)):
		add(f"FST-ACS-M{m}", f"Allen Cap Screw M{m}x25 12.9 (box of 100)", "Fasteners", "Box", rate, 7)

	for size, rate in (("25x40x7", 38), ("30x47x7", 45), ("35x52x7", 55), ("40x62x8", 72)):
		add(f"SEAL-OS-{size}", f"Oil Seal {size} NBR", "Seals & O-Rings", "Nos", rate, 7)
	for size, rate in (("20x3", 6), ("30x3", 8), ("50x4", 14)):
		add(f"SEAL-OR-{size}", f"O-Ring NBR {size}", "Seals & O-Rings", "Nos", rate, 5)
	add("SEAL-MS-25", "Mechanical Seal 25mm Carbon/Ceramic", "Seals & O-Rings", "Nos", 640, 10)

	for hp, rate in (("0.5", 6400), ("1", 8200), ("2", 11800), ("3", 15200), ("5", 22600), ("7.5", 31800)):
		add(f"ELE-MTR-{hp.replace('.', '')}HP", f"Induction Motor {hp} HP 4-Pole 415V", "Electrical", "Nos", rate, 14)
	add("ELE-CON-9A", "Contactor 9A 3-Pole 230V coil", "Electrical", "Nos", 980, 7)
	add("ELE-CON-18A", "Contactor 18A 3-Pole 230V coil", "Electrical", "Nos", 1650, 7)
	add("ELE-MCB-16", "MCB 16A Triple Pole", "Electrical", "Nos", 720, 5)
	add("ELE-OLR-10", "Thermal Overload Relay 7-10A", "Electrical", "Nos", 1150, 7)
	add("ELE-CBL-15", "Copper Cable 1.5 sqmm 3-Core", "Electrical", "Meter", 62, 5)
	add("ELE-CBL-25", "Copper Cable 2.5 sqmm 3-Core", "Electrical", "Meter", 96, 5)
	add("ELE-PRX-M18", "Inductive Proximity Sensor M18 PNP", "Electrical", "Nos", 1380, 10)
	add("ELE-TB-4", "Terminal Box with Gland Plate", "Electrical", "Nos", 340, 7)
	add("ELE-CAP-25", "Run Capacitor 25uF 440V", "Electrical", "Nos", 210, 7)

	add("HYD-HOSE-12", "Hydraulic Hose 1/2in 2-Wire", "Hydraulics & Pneumatics", "Meter", 260, 7)
	add("HYD-FIT-12", "Hydraulic Hose Fitting 1/2in BSP", "Hydraulics & Pneumatics", "Nos", 145, 7)
	add("HYD-GEAR-Z20", "Spur Gear Module 2 Z20 EN8", "Hydraulics & Pneumatics", "Nos", 780, 14)
	add("HYD-GEAR-Z40", "Spur Gear Module 2 Z40 EN8", "Hydraulics & Pneumatics", "Nos", 1340, 14)
	add("HYD-CPL-L100", "Jaw Coupling L-100 with Spider", "Hydraulics & Pneumatics", "Nos", 690, 7)
	add("HYD-RV-12", "Pressure Relief Valve 1/2in 210 bar", "Hydraulics & Pneumatics", "Nos", 2450, 14)
	add("HYD-DCV-4", "Directional Control Valve 4/3 CETOP-3", "Hydraulics & Pneumatics", "Nos", 6800, 18)
	add("HYD-TANK-40", "Hydraulic Reservoir 40L MS", "Hydraulics & Pneumatics", "Nos", 5200, 14)
	add("PNU-SV-14", "Solenoid Valve 5/2 1/4in 24VDC", "Hydraulics & Pneumatics", "Nos", 1850, 10)
	add("PNU-CYL-50", "Pneumatic Cylinder 50x100", "Hydraulics & Pneumatics", "Nos", 3100, 10)

	for code, name, uom, rate in (
		("CON-CUTOIL", "Soluble Cutting Oil", "Litre", 165),
		("CON-HYDOIL68", "Hydraulic Oil ISO VG 68", "Litre", 142),
		("CON-GREASE-EP2", "Lithium Grease EP2", "Kg", 210),
		("CON-ELEC-6013", "Welding Electrode E6013 3.15mm", "Kg", 185),
		("CON-MIG-12", "MIG Wire ER70S-6 1.2mm", "Kg", 155),
		("CON-GW-4", "Grinding Wheel 4in", "Nos", 48),
		("CON-CW-14", "Cut-off Wheel 14in", "Nos", 165),
		("CON-EMERY-120", "Emery Paper Grit 120 (pack of 50)", "Box", 420),
		("CON-PAINT-BLU", "Synthetic Enamel Paint RAL 5015 Blue", "Litre", 320),
		("CON-PRIMER-RO", "Red Oxide Primer", "Litre", 190),
		("CON-THINNER", "NC Thinner", "Litre", 95),
		("CON-COTWASTE", "Cotton Waste", "Kg", 70),
		("CON-GLOVES", "Leather Safety Gloves", "Pair", 85),
		("CON-GOGGLES", "Safety Goggles Clear", "Nos", 120),
		("CON-EARPLUG", "Foam Ear Plugs (box of 200)", "Box", 1450),
		("CON-ARGON", "Argon Gas Cylinder Refill 7 cum", "Nos", 1800),
		("CON-OXY", "Oxygen Cylinder Refill 7 cum", "Nos", 520),
		("CON-COOLANT", "Synthetic Coolant Concentrate", "Litre", 260),
		("CON-TAPE-48", "Masking Tape 48mm", "Nos", 55),
		("CON-DEGREASE", "Industrial Degreaser", "Litre", 175),
	):
		add(code, name, "Consumable", uom, rate, 4)

	for code, name, rate in (
		("MRO-VB-A42", "V-Belt A42", 210), ("MRO-VB-A52", "V-Belt A52", 245), ("MRO-VB-B64", "V-Belt B64", 390),
		("MRO-TB-8M", "Timing Belt 8M-1200-30", 1650),
		("MRO-DRL-6", "HSS Drill Bit 6mm", 45), ("MRO-DRL-8", "HSS Drill Bit 8mm", 70),
		("MRO-DRL-10", "HSS Drill Bit 10mm", 105), ("MRO-DRL-12", "HSS Drill Bit 12mm", 150),
		("MRO-EM-6", "Carbide End Mill 6mm 4F", 680), ("MRO-EM-10", "Carbide End Mill 10mm 4F", 1180),
		("MRO-EM-12", "Carbide End Mill 12mm 4F", 1560),
		("MRO-TAP-M8", "HSS Machine Tap M8", 240), ("MRO-TAP-M10", "HSS Machine Tap M10", 310),
		("MRO-INS-CNMG", "Turning Insert CNMG 120408 (box of 10)", 3400),
		("MRO-INS-WNMG", "Turning Insert WNMG 080408 (box of 10)", 3150),
		("MRO-FLT-HYD", "Hydraulic Return Filter Element 10 micron", 1450),
		("MRO-FLT-AIR", "Compressor Air Filter Element", 980),
		("MRO-RLY-24", "Control Relay 24VDC 2CO", 260),
		("MRO-LS-01", "Limit Switch Roller Lever", 540),
		("MRO-SPR-NOZ", "Spray Gun Nozzle 1.5mm", 380),
		("MRO-CHK-KEY", "Lathe Chuck Key 10in", 290),
		("MRO-LAMP-LED", "LED High Bay Lamp 100W", 2650),
	):
		uom = "Box" if "box of" in name else "Nos"
		add(code, name, "MRO Spares", uom, rate, 6)

	for code, name, uom, rate in (
		("PKG-BOX-S", "Corrugated Box 5-Ply Small", "Nos", 48),
		("PKG-BOX-M", "Corrugated Box 5-Ply Medium", "Nos", 78),
		("PKG-BOX-L", "Corrugated Box 7-Ply Large", "Nos", 135),
		("PKG-CRATE", "Wooden Crate Heat-Treated", "Nos", 1250),
		("PKG-STRETCH", "Stretch Film Roll 500mm", "Nos", 420),
		("PKG-BUBBLE", "Bubble Wrap 1m width", "Meter", 18),
		("PKG-PALLET", "Wooden Pallet 1200x1000", "Nos", 780),
		("PKG-VCI", "VCI Bag 450x600", "Nos", 22),
	):
		add(code, name, "Packaging", uom, rate, 5)

	for code, name, rate in (
		("IT-LAP-14", "Laptop 14in Core i5 16GB 512GB SSD", 68500),
		("IT-DSK-I5", "Desktop Core i5 16GB 512GB SSD", 52000),
		("IT-MON-24", "Monitor 24in IPS FHD", 11800),
		("IT-PRN-LJ", "Laser Printer Mono Duplex", 18900),
		("IT-TONER", "Toner Cartridge for Laser Printer", 3400),
		("IT-MOUSE", "Wireless Mouse", 650),
		("IT-KBD", "USB Keyboard", 720),
		("IT-UPS-1K", "Line Interactive UPS 1kVA", 6200),
		("IT-SW-24", "Managed Network Switch 24-Port Gigabit", 23500),
		("IT-RTR", "Business Router Dual WAN", 14200),
		("IT-SSD-1T", "SSD 1TB NVMe", 6900),
		("IT-CAM", "HD Webcam 1080p", 3100),
		("IT-HEADSET", "USB Headset with Mic", 2200),
		("IT-TAB-10", "Android Tablet 10in for Shop Floor", 21500),
		("IT-SCAN", "Handheld Barcode Scanner 2D", 7800),
	):
		add(code, name, "IT Equipment", "Nos", rate, 7)

	for code, name, uom, rate in (
		("OFF-A4", "A4 Copier Paper 75gsm (box of 5 reams)", "Box", 1350),
		("OFF-PEN", "Ball Pen Blue (box of 50)", "Box", 280),
		("OFF-NOTE", "Notebook A5 200 pages", "Nos", 65),
		("OFF-STAPLER", "Stapler with Pins", "Nos", 180),
		("OFF-FILE", "Box File Lever Arch", "Nos", 120),
		("OFF-MARKER", "Whiteboard Marker (box of 10)", "Box", 260),
		("OFF-WATER", "Drinking Water Can 20L", "Nos", 45),
		("OFF-TEA", "Tea and Coffee Supplies Monthly Kit", "Nos", 3800),
		("OFF-HK", "Housekeeping Consumables Kit", "Nos", 2900),
		("OFF-ENV", "Courier Envelope A4 (pack of 50)", "Box", 340),
	):
		add(code, name, "Office Supplies", uom, rate, 3)

	for code, name, uom, rate in (
		("SRV-AMC-CNC", "CNC Machine Annual Maintenance Contract (quarterly)", "Unit", 145000),
		("SRV-CALIB", "Instrument Calibration Service", "Unit", 18500),
		("SRV-FREIGHT", "Outbound Freight Charges", "Unit", 9500),
		("SRV-HK", "Housekeeping Service (monthly)", "Unit", 68000),
		("SRV-SECURITY", "Security Service (monthly)", "Unit", 92000),
		("SRV-PRESS-OH", "Hydraulic Press Overhaul", "Unit", 485000),
		("SRV-ELEC-MAINT", "Electrical Preventive Maintenance (monthly)", "Unit", 42000),
		("SRV-SOFTWARE", "CAD Software Subscription (annual)", "Unit", 265000),
	):
		add(code, name, "Services", uom, rate, 2)

	return items


ITEMS = _items()

# Finished goods: code, name, uom, selling rate, BOM {component: qty per unit}.
FINISHED_GOODS = [
	("FG-HGP-10", "Hydraulic Gear Pump HGP-10", 14500, {
		"RM-CI-PB10": 1, "HYD-GEAR-Z20": 2, "RM-EN8-20": 1.2, "BRG-6202": 2, "SEAL-OS-25x40x7": 1,
		"SEAL-OR-20x3": 2, "FST-ACS-M6": 0.08, "CON-PAINT-BLU": 0.15, "PKG-BOX-S": 1}),
	("FG-HGP-20", "Hydraulic Gear Pump HGP-20", 21500, {
		"RM-CI-PB20": 1, "HYD-GEAR-Z20": 2, "RM-EN8-32": 1.8, "BRG-6204": 2, "SEAL-OS-30x47x7": 1,
		"SEAL-OR-30x3": 2, "FST-ACS-M8": 0.08, "CON-PAINT-BLU": 0.2, "PKG-BOX-M": 1}),
	("FG-HGP-40", "Hydraulic Gear Pump HGP-40", 34800, {
		"RM-CI-PB40": 1, "HYD-GEAR-Z40": 2, "RM-EN8-50": 2.6, "BRG-6206": 2, "SEAL-OS-40x62x8": 1,
		"SEAL-OR-50x4": 2, "FST-ACS-M10": 0.08, "CON-PAINT-BLU": 0.3, "PKG-BOX-L": 1}),
	("FG-CP-50", "Centrifugal Pump CP-50 with 2HP Motor", 32500, {
		"RM-CI-CP": 1, "RM-AL-IMP": 1, "RM-SS304-2": 1.5, "SEAL-MS-25": 1, "BRG-6205": 2, "ELE-MTR-2HP": 1,
		"FST-HB-M10x40": 0.06, "FST-HN-M10": 0.06, "CON-PAINT-BLU": 0.35, "PKG-CRATE": 1}),
	("FG-CP-80", "Centrifugal Pump CP-80 with 3HP Motor", 41800, {
		"RM-CI-CP": 1, "RM-AL-IMP": 1, "RM-SS304-3": 2, "SEAL-MS-25": 1, "BRG-6206": 2, "ELE-MTR-3HP": 1,
		"FST-HB-M12x40": 0.06, "FST-HN-M12": 0.06, "CON-PAINT-BLU": 0.4, "PKG-CRATE": 1}),
	("FG-CP-100", "Centrifugal Pump CP-100 with 5HP Motor", 56900, {
		"RM-CI-CP": 1, "RM-AL-IMP": 1, "RM-SS316-40": 2.4, "SEAL-MS-25": 1, "BRG-6208": 2, "ELE-MTR-5HP": 1,
		"FST-HB-M12x60": 0.08, "FST-HN-M12": 0.08, "CON-PAINT-BLU": 0.5, "PKG-CRATE": 1}),
	("FG-MB-1HP", "Monoblock Pump MB-1HP", 15800, {
		"RM-AL-IMP": 1, "RM-SS304-1": 1.2, "ELE-MTR-1HP": 1, "SEAL-MS-25": 1, "ELE-CAP-25": 1,
		"FST-HB-M8x25": 0.05, "CON-PAINT-BLU": 0.15, "PKG-BOX-M": 1}),
	("FG-MB-2HP", "Monoblock Pump MB-2HP", 21900, {
		"RM-AL-IMP": 1, "RM-SS304-2": 1.6, "ELE-MTR-2HP": 1, "SEAL-MS-25": 1, "ELE-CAP-25": 1,
		"FST-HB-M10x25": 0.05, "CON-PAINT-BLU": 0.2, "PKG-BOX-L": 1}),
	("FG-GB-100", "Gearbox Assembly GB-100 Ratio 10:1", 38500, {
		"RM-CI-GB": 1, "HYD-GEAR-Z20": 1, "HYD-GEAR-Z40": 1, "RM-EN8-50": 3, "BRG-30205": 2, "BRG-6207": 2,
		"SEAL-OS-35x52x7": 2, "CON-HYDOIL68": 1.5, "FST-HB-M10x60": 0.1, "PKG-CRATE": 1}),
	("FG-GB-200", "Gearbox Assembly GB-200 Ratio 20:1", 54200, {
		"RM-CI-GB": 1, "HYD-GEAR-Z20": 2, "HYD-GEAR-Z40": 2, "RM-EN8-75": 3.5, "BRG-30206": 2, "BRG-32210": 1,
		"BRG-6209": 2, "SEAL-OS-40x62x8": 2, "CON-HYDOIL68": 2.5, "FST-HB-M12x60": 0.12, "PKG-CRATE": 1}),
	("FG-VA-25", "Valve Assembly VA-25 Brass", 6400, {
		"RM-BR-20": 1.4, "SEAL-OR-20x3": 3, "RM-PTFE-3": 0.1, "FST-ACS-M6": 0.04, "PKG-BOX-S": 1}),
	("FG-VA-50", "Valve Assembly VA-50 SS316", 12800, {
		"RM-SS316-25": 2.2, "SEAL-OR-50x4": 3, "RM-PTFE-3": 0.2, "FST-ACS-M8": 0.04, "PKG-BOX-M": 1}),
	("FG-MCK-1", "Motor Coupling Kit MCK-1", 2900, {
		"HYD-CPL-L100": 1, "RM-AL6061-25": 0.6, "FST-HB-M8x40": 0.04, "FST-SW-M8": 0.04, "PKG-BOX-S": 1}),
	("FG-MCK-2", "Motor Coupling Kit MCK-2", 4300, {
		"HYD-CPL-L100": 1, "RM-AL6061-50": 0.9, "FST-HB-M10x40": 0.04, "FST-SW-M10": 0.04, "PKG-BOX-S": 1}),
	("FG-HPP-5", "Hydraulic Power Pack HPP-5", 128000, {
		"HYD-TANK-40": 1, "ELE-MTR-5HP": 1, "HYD-RV-12": 1, "HYD-DCV-4": 2, "HYD-HOSE-12": 4, "HYD-FIT-12": 6,
		"HYD-CPL-L100": 1, "ELE-CON-18A": 1, "ELE-OLR-10": 1, "ELE-CBL-25": 5, "CON-HYDOIL68": 35,
		"MRO-FLT-HYD": 1, "CON-PAINT-BLU": 0.8, "PKG-PALLET": 1, "PKG-STRETCH": 1}),
]

# Relative weekly demand for each finished good (units/week at medium scale).
FG_WEEKLY_DEMAND = {
	"FG-HGP-10": 14, "FG-HGP-20": 10, "FG-HGP-40": 5, "FG-CP-50": 6, "FG-CP-80": 4, "FG-CP-100": 2,
	"FG-MB-1HP": 12, "FG-MB-2HP": 8, "FG-GB-100": 3, "FG-GB-200": 2, "FG-VA-25": 18, "FG-VA-50": 7,
	"FG-MCK-1": 15, "FG-MCK-2": 10, "FG-HPP-5": 1,
}

# Monthly indirect consumption (qty/month) for non-BOM stock items, by group.
INDIRECT_MONTHLY = {
	"Consumable": (4, 40),
	"MRO Spares": (1, 8),
	"Packaging": (5, 40),
	"Office Supplies": (2, 20),
	"IT Equipment": (0, 2),
}

# Suppliers: name, group, state, item groups supplied, profile.
# profile: on_time (probability), delay (max days late), reject (max reject fraction),
# price (multiplier on base rate), terms (payment terms template).
SUPPLIERS = [
	("Shree Ganesh Steels", "Raw Material", "Maharashtra", ["Steel"], dict(on_time=0.92, delay=6, reject=0.01, price=1.00, terms="Net 45")),
	("Mahalaxmi Metal Corporation", "Raw Material", "Maharashtra", ["Steel", "Non-Ferrous Metals"], dict(on_time=0.78, delay=12, reject=0.02, price=0.97, terms="Net 30")),
	("Bharat Alloys and Metals", "Raw Material", "Gujarat", ["Non-Ferrous Metals", "Steel"], dict(on_time=0.88, delay=8, reject=0.015, price=1.02, terms="Net 45")),
	("Deccan Steel Traders", "Raw Material", "Karnataka", ["Steel"], dict(on_time=0.65, delay=15, reject=0.03, price=0.94, terms="Net 30")),
	("Kolhapur Foundry Works", "Raw Material", "Maharashtra", ["Castings"], dict(on_time=0.72, delay=14, reject=0.06, price=0.98, terms="Net 60")),
	("Rajkot Castings Pvt Ltd", "Raw Material", "Gujarat", ["Castings"], dict(on_time=0.86, delay=9, reject=0.025, price=1.04, terms="Net 45")),
	("Polyflex Industries", "Raw Material", "Maharashtra", ["Polymers & Rubber"], dict(on_time=0.95, delay=4, reject=0.01, price=1.00, terms="Net 30")),
	("Precision Bearing House", "Components", "Maharashtra", ["Bearings"], dict(on_time=0.96, delay=3, reject=0.002, price=1.03, terms="Net 30")),
	("National Bearing Agencies", "Components", "Tamil Nadu", ["Bearings"], dict(on_time=0.84, delay=7, reject=0.01, price=0.96, terms="Net 45")),
	("Allied Bearings Pvt Ltd", "Components", "Gujarat", ["Bearings"], dict(on_time=0.9, delay=5, reject=0.004, price=1.00, terms="Net 30")),
	("Kumar Fasteners", "Components", "Maharashtra", ["Fasteners"], dict(on_time=0.94, delay=4, reject=0.005, price=1.00, terms="Net 30")),
	("Metro Bolts and Nuts", "Components", "Maharashtra", ["Fasteners"], dict(on_time=0.8, delay=8, reject=0.02, price=0.93, terms="Net 30")),
	("Ludhiana Fastener Company", "Components", "Punjab", ["Fasteners"], dict(on_time=0.75, delay=12, reject=0.015, price=0.9, terms="Net 60")),
	("Sealwell Industries", "Components", "Maharashtra", ["Seals & O-Rings"], dict(on_time=0.93, delay=4, reject=0.01, price=1.00, terms="Net 30")),
	("Durable Seals and Gaskets", "Components", "Karnataka", ["Seals & O-Rings"], dict(on_time=0.82, delay=9, reject=0.03, price=0.95, terms="Net 45")),
	("Om Sai Electric Motors", "Components", "Maharashtra", ["Electrical"], dict(on_time=0.85, delay=10, reject=0.008, price=1.00, terms="Net 45")),
	("Shakti Electricals", "Components", "Maharashtra", ["Electrical"], dict(on_time=0.9, delay=6, reject=0.005, price=1.02, terms="Net 30")),
	("Volta Switchgear Traders", "Components", "Gujarat", ["Electrical"], dict(on_time=0.7, delay=12, reject=0.012, price=0.95, terms="Net 30")),
	("Hydrotech Engineers", "Components", "Maharashtra", ["Hydraulics & Pneumatics"], dict(on_time=0.88, delay=8, reject=0.01, price=1.00, terms="Net 45")),
	("FluidPower Systems", "Components", "Tamil Nadu", ["Hydraulics & Pneumatics"], dict(on_time=0.8, delay=10, reject=0.015, price=0.97, terms="Net 45")),
	("Gearcraft Precision", "Components", "Maharashtra", ["Hydraulics & Pneumatics"], dict(on_time=0.68, delay=16, reject=0.04, price=0.95, terms="Net 60")),
	("Western Industrial Supplies", "Consumables", "Maharashtra", ["Consumable"], dict(on_time=0.95, delay=3, reject=0.0, price=1.00, terms="Net 30")),
	("Welding Mart", "Consumables", "Maharashtra", ["Consumable"], dict(on_time=0.9, delay=4, reject=0.01, price=0.98, terms="Net 15")),
	("Lubetech Oils", "Consumables", "Gujarat", ["Consumable"], dict(on_time=0.87, delay=6, reject=0.0, price=1.01, terms="Net 30")),
	("Toolcraft India", "MRO", "Maharashtra", ["MRO Spares"], dict(on_time=0.9, delay=5, reject=0.01, price=1.00, terms="Net 30")),
	("Precision Tooling Solutions", "MRO", "Karnataka", ["MRO Spares"], dict(on_time=0.83, delay=8, reject=0.02, price=0.96, terms="Net 30")),
	("Pack-Rite Packaging", "Packaging", "Maharashtra", ["Packaging"], dict(on_time=0.93, delay=4, reject=0.01, price=1.00, terms="Net 30")),
	("Sahyadri Corrugators", "Packaging", "Maharashtra", ["Packaging"], dict(on_time=0.79, delay=7, reject=0.03, price=0.92, terms="Net 30")),
	("Infotech Systems", "IT", "Maharashtra", ["IT Equipment"], dict(on_time=0.9, delay=5, reject=0.0, price=1.00, terms="Net 30")),
	("Digital Edge Computers", "IT", "Karnataka", ["IT Equipment"], dict(on_time=0.85, delay=7, reject=0.0, price=0.97, terms="Net 15")),
	("Laptop World Pune", "IT", "Maharashtra", ["IT Equipment"], dict(on_time=0.8, delay=6, reject=0.0, price=1.04, terms="Immediate")),
	("Office Mart Stationers", "Office", "Maharashtra", ["Office Supplies"], dict(on_time=0.97, delay=2, reject=0.0, price=1.00, terms="Net 15")),
	("Kalpana Stationery", "Office", "Maharashtra", ["Office Supplies"], dict(on_time=0.9, delay=3, reject=0.0, price=0.95, terms="Immediate")),
	("Accurate Calibration Labs", "Services", "Maharashtra", ["SRV-CALIB"], dict(on_time=0.95, delay=3, reject=0.0, price=1.00, terms="Net 30")),
	("SwiftMove Logistics", "Services", "Maharashtra", ["SRV-FREIGHT"], dict(on_time=0.95, delay=2, reject=0.0, price=1.00, terms="Net 15")),
	("CleanPro Facility Services", "Services", "Maharashtra", ["SRV-HK"], dict(on_time=1.0, delay=0, reject=0.0, price=1.00, terms="Net 30")),
	("Guardian Security Services", "Services", "Maharashtra", ["SRV-SECURITY"], dict(on_time=1.0, delay=0, reject=0.0, price=1.00, terms="Net 30")),
	("MachineCare AMC Services", "Services", "Maharashtra", ["SRV-AMC-CNC", "SRV-PRESS-OH", "SRV-ELEC-MAINT"], dict(on_time=0.9, delay=4, reject=0.0, price=1.00, terms="Net 45")),
	("Designsoft Technologies", "Services", "Karnataka", ["SRV-SOFTWARE"], dict(on_time=1.0, delay=0, reject=0.0, price=1.00, terms="Net 30")),
	("Express Industrial Traders", "Components", "Maharashtra", ["Fasteners", "Electrical", "Bearings", "Consumable"], dict(on_time=0.7, delay=10, reject=0.03, price=1.12, terms="Immediate")),
]

SUPPLIER_GROUPS = ["Raw Material", "Components", "Consumables", "MRO", "Packaging", "IT", "Office", "Services"]

# Customers: name, group, territory, state, payment terms, payment behaviour (days late max).
CUSTOMERS = [
	("Sahyadri Agro Industries", "Commercial", "West India", "Maharashtra", "Net 30", 10),
	("Nashik Water Solutions", "Commercial", "West India", "Maharashtra", "Net 30", 5),
	("Godavari Sugar Mills", "Commercial", "West India", "Maharashtra", "Net 45", 25),
	("Coastal Aquaculture Ltd", "Commercial", "South India", "Andhra Pradesh", "Net 45", 15),
	("Metro Infra Projects", "Commercial", "West India", "Maharashtra", "Net 60", 40),
	("Ganga Irrigation Supplies", "Distributor", "North India", "Uttar Pradesh", "Net 30", 12),
	("Narmada Pumps and Motors", "Distributor", "West India", "Gujarat", "Net 30", 6),
	("Kaveri Engineering Stores", "Distributor", "South India", "Karnataka", "Net 30", 8),
	("Punjab Agri Equipment Co", "Distributor", "North India", "Punjab", "Net 45", 20),
	("Bengal Fluid Systems", "Distributor", "East India", "West Bengal", "Net 45", 18),
	("Rajasthan Hydraulics", "Distributor", "North India", "Rajasthan", "Net 30", 10),
	("Orbit Machine Tools", "Commercial", "West India", "Maharashtra", "Net 30", 3),
	("Vishwakarma Press Works", "Commercial", "West India", "Maharashtra", "Net 30", 9),
	("Southern Textile Mills", "Commercial", "South India", "Tamil Nadu", "Net 45", 14),
	("Pune Municipal Water Works", "Government", "West India", "Maharashtra", "Net 60", 55),
	("Maharashtra Jeevan Pradhikaran", "Government", "West India", "Maharashtra", "Net 60", 45),
	("Hindustan Process Plants", "Commercial", "West India", "Gujarat", "Net 45", 7),
	("Delta Chemicals Ltd", "Commercial", "West India", "Gujarat", "Net 30", 4),
	("Konkan Fisheries Cooperative", "Commercial", "West India", "Maharashtra", "Net 30", 30),
	("Telangana Lift Irrigation", "Government", "South India", "Telangana", "Net 60", 60),
	("Excel Hydraulic Presses", "Commercial", "West India", "Maharashtra", "Net 30", 5),
	("Bharat Earthmovers Services", "Commercial", "South India", "Karnataka", "Net 45", 12),
	("Prime Fire Protection", "Commercial", "West India", "Maharashtra", "Net 30", 8),
	("Eastern Power Equipments", "Distributor", "East India", "Odisha", "Net 45", 22),
	("Indus Dairy Equipment", "Commercial", "North India", "Haryana", "Net 30", 6),
	("Shivam Pump Traders", "Distributor", "West India", "Maharashtra", "Net 15", 2),
	("Apollo Plastics Machinery", "Commercial", "West India", "Gujarat", "Net 30", 10),
	("Cauvery Building Services", "Commercial", "South India", "Karnataka", "Net 45", 16),
	("Northern Railway Workshop", "Government", "North India", "Delhi", "Net 60", 35),
	("Global Marine Engineering", "Commercial", "West India", "Goa", "Net 45", 18),
]

PAYMENT_TERMS = {"Immediate": 0, "Net 15": 15, "Net 30": 30, "Net 45": 45, "Net 60": 60}

WAREHOUSES = ["Stores", "Finished Goods", "Rejected Stores", "Chakan Plant Stores"]

COST_CENTERS = ["Production", "Maintenance", "Administration", "IT", "Sales and Marketing"]

# Users created for role-based testing: (first name, last name, local part, roles).
USERS = [
	("Priya", "Kulkarni", "priya.kulkarni", ["Purchase User", "Stock User"]),
	("Rahul", "Deshmukh", "rahul.deshmukh", ["Purchase User", "Stock User"]),
	("Anjali", "Mehta", "anjali.mehta", ["Purchase Manager", "Purchase User", "Purchase Master Manager", "Stock User"]),
	("Vikram", "Joshi", "vikram.joshi", ["Director", "Purchase Manager", "Purchase User", "Accounts Manager"]),
	("Suresh", "Patil", "suresh.patil", ["Stock User", "Stock Manager", "Manufacturing User"]),
	("Neha", "Iyer", "neha.iyer", ["Accounts User", "Accounts Manager"]),
	("Arjun", "Nair", "arjun.nair", ["Sales User", "Sales Manager"]),
	("Kavita", "Rao", "kavita.rao", ["Manufacturing User", "Manufacturing Manager", "Stock User"]),
]
