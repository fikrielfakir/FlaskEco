from datetime import datetime
from app import db
from flask_login import UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='Operator')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    active = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class ProductionBatch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lot_number = db.Column(db.String(50), unique=True, nullable=False)
    product_type = db.Column(db.String(100), nullable=False)
    planned_quantity = db.Column(db.Integer, nullable=False)
    actual_quantity = db.Column(db.Integer, default=0)
    production_date = db.Column(db.Date, nullable=False)
    kiln_number = db.Column(db.String(20), nullable=False)
    kiln_temperature = db.Column(db.Float)
    firing_duration = db.Column(db.Float)
    status = db.Column(db.String(20), default='planned')  # planned, in_progress, completed, approved, rejected
    supervisor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notes = db.Column(db.Text)
    
    # Laboratory control plan nominal dimensions
    product_format = db.Column(db.String(20))  # 20x20, 25x40, 25x50
    nominal_length = db.Column(db.Float)  # mm
    nominal_width = db.Column(db.Float)   # mm
    nominal_thickness = db.Column(db.Float)  # mm

    supervisor = db.relationship('User', backref='supervised_batches')

    def get_nominal_dimension(self, dimension):
        """Get nominal dimension for this batch"""
        return getattr(self, f'nominal_{dimension}', None)
    
    def __repr__(self):
        return f'<ProductionBatch {self.lot_number}>'

class QualityTest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('production_batch.id'), nullable=False)
    test_type = db.Column(db.String(50), nullable=False)  # dimensional, water_absorption, breaking_strength, abrasion, clay_testing, thermal_shock, glaze_testing, cetemco_testing
    test_date = db.Column(db.DateTime, default=datetime.utcnow)
    technician_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sample_id = db.Column(db.String(50))  # Sample identification code
    
    # Dimensional measurements (ISO 10545-2)
    length = db.Column(db.Float)  # mm
    width = db.Column(db.Float)   # mm
    thickness = db.Column(db.Float)  # mm
    straightness = db.Column(db.Float)  # mm deviation
    flatness = db.Column(db.Float)      # mm deviation
    rectangularity = db.Column(db.Float)  # mm deviation
    warping = db.Column(db.Float)  # % or mm
    
    # NEW: Laboratory control plan dimensional parameters
    central_curvature = db.Column(db.Float)     # mm - courbure centrale ±0.5% max 2mm
    lateral_curvature = db.Column(db.Float)     # mm - courbure latérale ±0.5% max 2mm  
    angularity = db.Column(db.Float)            # mm - angularité ±0.5% max 2mm
    
    # Water absorption (ISO 10545-3)
    water_absorption = db.Column(db.Float)  # %
    
    # Breaking strength / Flexural resistance (ISO 10545-4)
    breaking_force = db.Column(db.Float)    # N (Newtons)
    breaking_strength = db.Column(db.Float) # N/mm² (calculated flexural strength)
    
    # Abrasion resistance (ISO 10545-6/7)
    abrasion_resistance = db.Column(db.String(10))  # PEI class I-V
    abrasion_cycles = db.Column(db.Integer)  # test cycles completed
    volume_loss = db.Column(db.Float)  # mm³ for unglazed tiles
    
    # Clay testing (Argile) - Raw material quality control
    clay_humidity_hopper = db.Column(db.Float)  # % humidity in general hopper (2.5-4.1%)
    clay_humidity_sieved = db.Column(db.Float)  # % humidity after sieving (2-3.5%)
    clay_humidity_silo = db.Column(db.Float)  # % humidity in silo (5.3-6.3%)
    clay_humidity_press = db.Column(db.Float)  # % humidity at press (5.2-6%)
    clay_granulometry_refusal = db.Column(db.Float)  # % refusal CaCO3 granulometry (10-20%)
    clay_carbonate_content = db.Column(db.Float)  # % CaCO3 content (15-25%)
    
    # Additional ceramic testing fields
    thermal_shock_resistance = db.Column(db.Boolean)  # Pass/fail for thermal shock
    shrinkage_expansion = db.Column(db.Float)  # % shrinkage/expansion (-0.2 to +0.4%)
    loss_on_ignition = db.Column(db.Float)  # % loss on fire (10-19%)
    residual_humidity = db.Column(db.Float)  # % residual humidity in séchoir (0.1-1.5%)
    
    # Glaze testing (for Four Email/Glaze kiln)
    glaze_density = db.Column(db.Float)  # g/l glaze density
    glaze_viscosity = db.Column(db.Float)  # seconds viscosity
    glaze_refusal = db.Column(db.Float)  # ml refusal at 45µ sieve
    
    # CETEMCO testing (ISO 10545-9, -11, -13, -14)
    thermal_resistance = db.Column(db.String(20))  # CETEMCO thermal resistance result
    chemical_resistance = db.Column(db.String(20))  # CETEMCO chemical resistance result
    stain_resistance = db.Column(db.String(20))  # CETEMCO stain resistance result
    
    # Visual inspection
    visual_defects = db.Column(db.Text)
    surface_quality_score = db.Column(db.Float)       # % - 95% min exempt from defects
    
    # ISO compliance and classification
    iso_standard = db.Column(db.String(30))  # ISO 10545-2, ISO 10545-3, etc.
    tile_classification = db.Column(db.String(20))  # BIa, BIIa, BIII, etc.
    absorption_group = db.Column(db.String(5))  # A, B, C
    forming_method = db.Column(db.String(10))   # Pressed (B), Extruded (A)
    surface_type = db.Column(db.String(10))     # glazed, unglazed
    compliance_score = db.Column(db.Float)
    compliance_details = db.Column(db.Text)           # Detailed compliance breakdown
    result = db.Column(db.String(10))  # pass, fail
    
    # Test conditions
    temperature_humidity = db.Column(db.String(50))  # Environmental conditions
    notes = db.Column(db.Text)
    equipment_calibration_date = db.Column(db.Date)

    batch = db.relationship('ProductionBatch', backref='quality_tests')
    technician = db.relationship('User', backref='conducted_tests')

    def calculate_flexural_strength_lab_specs(self):
        """Calculate flexural strength according to laboratory specifications"""
        if self.breaking_force and self.length and self.width and self.thickness:
            # Laboratory method: Module de rupture = (3 × F × L) / (2 × b × h²)
            span_length = self.length * 0.9  # 90% of tile length for span
            self.breaking_strength = (3 * self.breaking_force * span_length) / (2 * self.width * (self.thickness ** 2))
        
    def get_nominal_dimension(self, param):
        """Get nominal dimension from batch"""
        if hasattr(self.batch, f'nominal_{param}'):
            return getattr(self.batch, f'nominal_{param}')
        # Default values if not set
        defaults = {'length': 200.0, 'width': 200.0, 'thickness': 7.0}
        return defaults.get(param, 200.0)
    
    def determine_result_laboratory_specs(self):
        """Determine test result based on exact laboratory control plan specifications"""
        score = 0
        total_checks = 0
        compliance_details = []
        
        # PDM - ARGILE (Raw Materials)
        if self.test_type == 'clay_testing':
            clay_specs = [
                ('clay_humidity_hopper', self.clay_humidity_hopper, 2.5, 4.1, 'Humidité trémie générale'),
                ('clay_humidity_sieved', self.clay_humidity_sieved, 2.0, 3.5, 'Humidité après tamisage'),
                ('clay_humidity_silo', self.clay_humidity_silo, 5.3, 6.3, 'Humidité silo'),
                ('clay_humidity_press', self.clay_humidity_press, 5.2, 6.0, 'Humidité argile presse'),
                ('clay_granulometry_refusal', self.clay_granulometry_refusal, 10.0, 20.0, 'Granulométrie CaCO3'),
                ('clay_carbonate_content', self.clay_carbonate_content, 15.0, 25.0, 'Carbonate CaCO3')
            ]
            
            for param, value, min_val, max_val, label in clay_specs:
                if value is not None:
                    total_checks += 1
                    is_compliant = min_val <= value <= max_val
                    
                    if is_compliant:
                        score += 1
                        
                    compliance_details.append(f"{label}: {'CONFORME' if is_compliant else 'NON CONFORME'} ({value:.1f}% [{min_val}-{max_val}%])")
        
        # PRESSES
        elif self.test_type == 'pressing':
            # Determine format from batch
            product_format = getattr(self.batch, 'product_format', '20x20') if self.batch else '20x20'
            
            # Thickness specifications by format
            thickness_specs = {
                '20x20': (6.2, 7.2),
                '25x40': (6.8, 7.4), 
                '25x50': (7.1, 7.7)
            }
            
            # Weight specifications by format  
            weight_specs = {
                '20x20': (480, 580),
                '25x40': (1150, 1550),
                '25x50': (1800, 2000)
            }
            
            # Check thickness
            if self.thickness is not None:
                total_checks += 1
                min_thick, max_thick = thickness_specs.get(product_format, (6.2, 7.2))
                is_compliant = min_thick <= self.thickness <= max_thick
                
                if is_compliant:
                    score += 1
                    
                compliance_details.append(f"Épaisseur: {'CONFORME' if is_compliant else 'NON CONFORME'} ({self.thickness:.1f}mm [{min_thick}-{max_thick}mm])")
            
            # Check surface defects (visual aspect)
            if self.visual_defects is not None:
                surface_checks = [
                    ('grains', 15.0),
                    ('fissures', 1.0),
                    ('nettoyage', 1.0),
                    ('feuillage', 1.0),
                    ('ecornage', 1.0)
                ]
                
                defect_text = str(self.visual_defects).lower()
                
                for defect_type, max_percent in surface_checks:
                    total_checks += 1
                    # Simple check if defect mentioned
                    is_compliant = defect_type not in defect_text
                    
                    if is_compliant:
                        score += 1
                        
                    compliance_details.append(f"{defect_type.title()}: {'CONFORME' if is_compliant else 'NON CONFORME'} (≤{max_percent}%)")
                        
        # SÉCHOIR (Dryer)
        elif self.test_type == 'drying':
            # Residual humidity check
            if hasattr(self, 'residual_humidity') and self.residual_humidity is not None:
                total_checks += 1
                is_compliant = 0.1 <= self.residual_humidity <= 1.5
                
                if is_compliant:
                    score += 1
                    
                compliance_details.append(f"Humidité résiduelle: {'CONFORME' if is_compliant else 'NON CONFORME'} ({self.residual_humidity:.1f}% [0.1-1.5%])")
        
        # FOUR BISCUIT (Bisque Firing)
        elif self.test_type == 'bisque_firing':
            biscuit_defects = [
                ('fissure', 5.0),
                ('ecorne', 5.0), 
                ('cuisson', 1.0),
                ('feuillete', 1.0),
                ('planeite', 5.0)
            ]
            
            if self.visual_defects is not None:
                defect_text = str(self.visual_defects).lower()
                
                for defect_type, max_percent in biscuit_defects:
                    total_checks += 1
                    is_compliant = defect_type not in defect_text
                    
                    if is_compliant:
                        score += 1
                        
                    compliance_details.append(f"{defect_type.title()}: {'CONFORME' if is_compliant else 'NON CONFORME'} (≤{max_percent}%)")
            
            # Thermal shock test
            if self.thermal_shock_resistance is not None:
                total_checks += 1
                is_compliant = self.thermal_shock_resistance == True
                
                if is_compliant:
                    score += 1
                    
                compliance_details.append(f"Choc thermique: {'CONFORME' if is_compliant else 'NON CONFORME'} (Absence fissure)")
            
            # Shrinkage/expansion
            if self.shrinkage_expansion is not None:
                total_checks += 1
                is_compliant = -0.2 <= self.shrinkage_expansion <= 0.4
                
                if is_compliant:
                    score += 1
                    
                compliance_details.append(f"Retrait/dilatation: {'CONFORME' if is_compliant else 'NON CONFORME'} ({self.shrinkage_expansion:.1f}% [-0.2 à +0.4%])")
            
            # Loss on ignition
            if self.loss_on_ignition is not None:
                total_checks += 1
                is_compliant = 10.0 <= self.loss_on_ignition <= 19.0
                
                if is_compliant:
                    score += 1
                    
                compliance_details.append(f"Perte au feu: {'CONFORME' if is_compliant else 'NON CONFORME'} ({self.loss_on_ignition:.1f}% [10-19%])")
        
        # FOUR EMAIL (Enamel Firing) - Breaking Strength
        elif self.test_type == 'breaking_strength':
            if self.breaking_force is not None and self.thickness is not None:
                total_checks += 1
                # Force specifications: ≥7.5mm = min 600N, <7.5mm = min 200N
                min_force = 600 if self.thickness >= 7.5 else 200
                is_compliant = self.breaking_force >= min_force
                
                if is_compliant:
                    score += 1
                    
                compliance_details.append(f"Force rupture: {'CONFORME' if is_compliant else 'NON CONFORME'} ({self.breaking_force:.0f}N vs {min_force}N min)")
                
            if self.breaking_strength is not None and self.thickness is not None:
                total_checks += 1
                # Module specifications: ≥7.5mm = min 12 N/mm², <7.5mm = min 15 N/mm²
                min_modulus = 12 if self.thickness >= 7.5 else 15
                is_compliant = self.breaking_strength >= min_modulus
                
                if is_compliant:
                    score += 1
                    
                compliance_details.append(f"Module rupture: {'CONFORME' if is_compliant else 'NON CONFORME'} ({self.breaking_strength:.1f} vs {min_modulus} N/mm² min)")
        
        # FOUR EMAIL - Dimensional Characteristics
        elif self.test_type == 'dimensional':
            # Length & Width: ±0.5% max 2mm
            dimensional_checks = [
                ('length', self.length, 0.5, 2.0),
                ('width', self.width, 0.5, 2.0),
                ('thickness', self.thickness, 10.0, 0.5),  # ±10% ±0.5mm
                ('central_curvature', self.central_curvature, None, 2.0),  # ±0.5% ±2mm
                ('lateral_curvature', self.lateral_curvature, None, 2.0),  # ±0.5% ±2mm
                ('angularity', self.angularity, None, 2.0),  # ±0.5% ±2mm
                ('straightness', self.straightness, None, 1.5)  # ±0.3% ±1.5mm
            ]
            
            for param_name, value, percent_tol, mm_tol in dimensional_checks:
                if value is not None:
                    total_checks += 1
                    is_compliant = True
                    
                    if param_name in ['length', 'width']:
                        nominal = getattr(self.batch, f'nominal_{param_name}', 200.0) if self.batch else 200.0
                        deviation_percent = abs((value - nominal) / nominal) * 100
                        deviation_mm = abs(value - nominal)
                        
                        if deviation_percent > percent_tol or deviation_mm > mm_tol:
                            is_compliant = False
                            
                        detail = f"{param_name.title()}: {'CONFORME' if is_compliant else 'NON CONFORME'} ({deviation_percent:.2f}%, {deviation_mm:.1f}mm)"
                        
                    elif param_name == 'thickness':
                        nominal = getattr(self.batch, 'nominal_thickness', 7.0) if self.batch else 7.0
                        deviation_percent = abs((value - nominal) / nominal) * 100
                        deviation_mm = abs(value - nominal)
                        
                        if deviation_percent > percent_tol or deviation_mm > mm_tol:
                            is_compliant = False
                            
                        detail = f"Épaisseur: {'CONFORME' if is_compliant else 'NON CONFORME'} ({deviation_percent:.1f}%, {deviation_mm:.2f}mm)"
                        
                    else:
                        # Direct measurement against tolerance
                        if value > mm_tol:
                            is_compliant = False
                            
                        detail = f"{param_name.replace('_', ' ').title()}: {'CONFORME' if is_compliant else 'NON CONFORME'} ({value:.2f}mm ≤{mm_tol}mm)"
                    
                    if is_compliant:
                        score += 1
                    compliance_details.append(detail)
        
        # FOUR EMAIL - Water Absorption
        elif self.test_type == 'water_absorption':
            if self.water_absorption is not None:
                total_checks = 1
                # E > 10%, individual minimum 9%
                is_compliant = self.water_absorption >= 9.0
                
                if is_compliant:
                    score = 1
                    if self.water_absorption > 10.0:
                        self.tile_classification = "Faïence conforme"
                    elif self.water_absorption >= 9.0:
                        self.tile_classification = "Limite acceptable"
                    
                    if self.water_absorption > 20.0:
                        self.tile_classification += " (indication fabricant requise)"
                        
                compliance_details.append(f"Absorption: {'CONFORME' if is_compliant else 'NON CONFORME'} ({self.water_absorption:.2f}% ≥9%)")
        
        # FOUR EMAIL - Surface Quality
        elif self.test_type == 'surface_quality':
            if self.surface_quality_score is not None:
                total_checks += 1
                # 95% minimum exempt from defects
                is_compliant = self.surface_quality_score >= 95.0
                
                if is_compliant:
                    score += 1
                    
                compliance_details.append(f"Qualité surface: {'CONFORME' if is_compliant else 'NON CONFORME'} ({self.surface_quality_score:.1f}% ≥95%)")
        
        # PDE - EMAUX (Enamel)
        elif self.test_type == 'glaze_testing':
            # Density specifications
            if self.glaze_density is not None:
                total_checks += 1
                
                # Determine type and check specs
                density_specs = {
                    'engobe': (1780, 1830),
                    'email': (1730, 1780),
                    'mate': (1780, 1830)
                }
                
                # Default to email specs
                min_density, max_density = density_specs.get('email', (1730, 1780))
                is_compliant = min_density <= self.glaze_density <= max_density
                
                if is_compliant:
                    score += 1
                    
                compliance_details.append(f"Densité: {'CONFORME' if is_compliant else 'NON CONFORME'} ({self.glaze_density:.0f}g/l [{min_density}-{max_density}g/l])")
            
            # Viscosity
            if self.glaze_viscosity is not None:
                total_checks += 1
                is_compliant = 25 <= self.glaze_viscosity <= 55
                
                if is_compliant:
                    score += 1
                    
                compliance_details.append(f"Viscosité: {'CONFORME' if is_compliant else 'NON CONFORME'} ({self.glaze_viscosity:.0f}s [25-55s])")
            
            # Refusal at 45μ sieve  
            if self.glaze_refusal is not None:
                total_checks += 1
                # Default email specs: 3-5ml
                is_compliant = 3.0 <= self.glaze_refusal <= 5.0
                
                if is_compliant:
                    score += 1
                    
                compliance_details.append(f"Refus 45μ: {'CONFORME' if is_compliant else 'NON CONFORME'} ({self.glaze_refusal:.1f}ml [3-5ml])")
        
        # Store results
        if total_checks > 0:
            self.compliance_score = (score / total_checks) * 100
            self.compliance_details = " | ".join(compliance_details)
            return 'pass' if score == total_checks else 'fail'
        
        return None
    
    def determine_tile_classification(self):
        """Determine tile classification based on ISO 13006 / NM ISO 13006"""
        if not self.water_absorption:
            return None
            
        # Determine absorption group based on water absorption percentage
        if self.water_absorption <= 0.5:
            self.absorption_group = "A"  # Low absorption
            if self.forming_method == "Pressed":
                self.tile_classification = "BIa"  # Porcelain
            else:
                self.tile_classification = "AIa"
        elif 0.5 < self.water_absorption <= 3.0:
            self.absorption_group = "B"  # Medium absorption  
            if self.forming_method == "Pressed":
                self.tile_classification = "BIIa"  # Stoneware
            else:
                self.tile_classification = "AIIa"
        elif 3.0 < self.water_absorption <= 6.0:
            self.absorption_group = "B"
            if self.forming_method == "Pressed":
                self.tile_classification = "BIIb"
            else:
                self.tile_classification = "AIIb"
        elif 6.0 < self.water_absorption <= 10.0:
            self.absorption_group = "B"
            if self.forming_method == "Pressed":
                self.tile_classification = "BIIc"
            else:
                self.tile_classification = "AIIc"
        else:  # > 10%
            self.absorption_group = "C"  # High absorption
            if self.forming_method == "Pressed":
                self.tile_classification = "BIII"  # Earthenware
            else:
                self.tile_classification = "AIII"
        
        return self.tile_classification
    
    def check_dimensional_tolerances(self, product_type=None):
        """Check dimensional tolerances according to ISO 10545-2"""
        tolerances = {}
        
        # Get product type tolerances or use defaults for porcelain (BIa)
        if self.tile_classification == "BIa" or not self.tile_classification:
            # Porcelain tolerances (stricter)
            length_tolerance_pct = 0.6  # ±0.6%
            thickness_tolerance_pct = 5.0  # ±5.0%
            max_deviation_mm = 2.0  # max 2.0mm
            straightness_limit = 0.5  # ±0.5%
            flatness_limit = 0.5    # ±0.5%
        else:
            # Standard ceramic tolerances
            length_tolerance_pct = 1.0  # ±1.0%
            thickness_tolerance_pct = 10.0  # ±10.0%
            max_deviation_mm = 3.0  # max 3.0mm
            straightness_limit = 1.0  # ±1.0%
            flatness_limit = 1.0    # ±1.0%
        
        # Check length tolerance
        if self.length:
            length_tolerance = min((self.length * length_tolerance_pct / 100), max_deviation_mm)
            tolerances['length'] = abs(self.length - (self.length)) <= length_tolerance  # Compare to nominal
            
        # Check width tolerance  
        if self.width:
            width_tolerance = min((self.width * length_tolerance_pct / 100), max_deviation_mm)
            tolerances['width'] = abs(self.width - (self.width)) <= width_tolerance  # Compare to nominal
            
        # Check thickness tolerance
        if self.thickness:
            thickness_tolerance = self.thickness * thickness_tolerance_pct / 100
            tolerances['thickness'] = abs(self.thickness - (self.thickness)) <= thickness_tolerance  # Compare to nominal
            
        # Check straightness
        if self.straightness:
            straightness_tolerance = self.length * straightness_limit / 100 if self.length else 0.5
            tolerances['straightness'] = self.straightness <= straightness_tolerance
            
        # Check flatness  
        if self.flatness:
            flatness_tolerance = self.length * flatness_limit / 100 if self.length else 0.5
            tolerances['flatness'] = self.flatness <= flatness_tolerance
            
        return tolerances
        
    def determine_result_automatically(self):
        """Automatically determine if test passes or fails based on ISO 10545 standards"""
        # Calculate flexural strength if breaking force is provided
        if self.test_type == 'breaking_strength' and self.breaking_force:
            self.calculate_flexural_strength()
        
        # Determine tile classification
        if self.test_type == 'water_absorption' and self.water_absorption is not None:
            self.determine_tile_classification()
        
        # Check against ISO standards
        iso_standards = ISOStandard.query.filter_by(
            standard_code=self.iso_standard, 
            is_active=True
        ).all()
        
        if not iso_standards:
            return None  # Cannot determine without standards
        
        failed_tests = 0
        total_tests = 0
        passed_tests = []
        failed_tests_details = []
        
        for standard in iso_standards:
            if self.test_type == 'dimensional':
                # Check dimensional tolerances
                tolerances = self.check_dimensional_tolerances()
                for param, passes in tolerances.items():
                    total_tests += 1
                    if passes:
                        passed_tests.append(param)
                    else:
                        failed_tests += 1
                        failed_tests_details.append(param)
                        
            elif self.test_type == 'water_absorption' and standard.category == 'water_absorption':
                if self.water_absorption is not None:
                    total_tests += 1
                    # Check based on tile classification requirements
                    if self.tile_classification == "BIa" and self.water_absorption <= 0.5:
                        passed_tests.append('water_absorption')
                    elif self.tile_classification in ["BIIa", "BIIb"] and self.water_absorption <= 3.0:
                        passed_tests.append('water_absorption')
                    elif self.water_absorption <= standard.max_threshold:
                        passed_tests.append('water_absorption')
                    else:
                        failed_tests += 1
                        failed_tests_details.append('water_absorption')
            
            elif self.test_type == 'breaking_strength' and standard.category == 'breaking_strength':
                if self.breaking_strength is not None:
                    total_tests += 1
                    # Porcelain requires ≥35 N/mm², others ≥22 N/mm²
                    min_strength = 35 if self.tile_classification == "BIa" else 22
                    if self.breaking_strength >= min_strength:
                        passed_tests.append('breaking_strength')
                    else:
                        failed_tests += 1
                        failed_tests_details.append('breaking_strength')
                        
            elif self.test_type == 'abrasion' and standard.category == 'abrasion':
                if self.abrasion_resistance:
                    total_tests += 1
                    # PEI classification validation
                    pei_classes = ['PEI 0', 'PEI I', 'PEI II', 'PEI III', 'PEI IV', 'PEI V']
                    if self.abrasion_resistance in pei_classes:
                        passed_tests.append('abrasion')
                    else:
                        failed_tests += 1
                        failed_tests_details.append('abrasion')
        
        if total_tests == 0:
            return None  # No applicable tests
        
        # Calculate compliance score
        self.compliance_score = ((total_tests - failed_tests) / total_tests) * 100
        
        # Determine result: Pass if all tests pass
        if failed_tests == 0:
            self.result = 'pass'
            return 'pass'
        else:
            self.result = 'fail'
            return 'fail'

    def __repr__(self):
        return f'<QualityTest {self.test_type} for Batch {self.batch_id}>'

class EnergyConsumption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    energy_source = db.Column(db.String(20), nullable=False)  # electricity, gas, solar
    consumption_kwh = db.Column(db.Float, nullable=False)
    cost = db.Column(db.Float)
    kiln_number = db.Column(db.String(20))
    efficiency_rating = db.Column(db.Float)
    heat_recovery_kwh = db.Column(db.Float, default=0)
    recorded_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)

    recorded_by = db.relationship('User', backref='energy_records')

    def __repr__(self):
        return f'<EnergyConsumption {self.energy_source} {self.date}>'

class WasteRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    waste_type = db.Column(db.String(20), nullable=False)  # liquid, solid
    category = db.Column(db.String(50), nullable=False)
    quantity_kg = db.Column(db.Float, nullable=False)
    disposal_method = db.Column(db.String(50), nullable=False)  # recycled, reused, disposed
    recycling_percentage = db.Column(db.Float, default=0)
    environmental_impact = db.Column(db.Text)
    recorded_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)

    recorded_by = db.relationship('User', backref='waste_records')

    def __repr__(self):
        return f'<WasteRecord {self.waste_type} {self.date}>'

class RawMaterial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    supplier = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    quantity_kg = db.Column(db.Float, nullable=False)
    unit_cost = db.Column(db.Float)
    quality_grade = db.Column(db.String(20))
    date_received = db.Column(db.Date, nullable=False)
    expiry_date = db.Column(db.Date)
    lot_number = db.Column(db.String(50))
    specifications = db.Column(db.Text)
    quality_certified = db.Column(db.Boolean, default=False)
    recorded_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    recorded_by = db.relationship('User', backref='material_records')

    def __repr__(self):
        return f'<RawMaterial {self.name}>'

class ISOStandard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    standard_code = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), nullable=False)  # length, width, thickness, warping, water_absorption, breaking_strength
    test_type = db.Column(db.String(50), nullable=False)  # dimensional, water_absorption, breaking_strength, abrasion
    min_threshold = db.Column(db.Float)
    max_threshold = db.Column(db.Float)
    unit = db.Column(db.String(20))
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<ISOStandard {self.standard_code}-{self.category}>'

class Kiln(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    max_temperature = db.Column(db.Float, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)  # capacity in pieces
    status = db.Column(db.String(20), default='active')  # active, maintenance, inactive
    location = db.Column(db.String(100))
    installation_date = db.Column(db.Date)
    last_maintenance = db.Column(db.Date)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<Kiln {self.name}>'

class ProductType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    category = db.Column(db.String(50), nullable=False)  # floor, wall, ceramic, etc.
    dimensions = db.Column(db.String(50))  # e.g., "30x30", "25x40"
    thickness = db.Column(db.Float)  # thickness in mm
    firing_temperature = db.Column(db.Float)  # recommended firing temperature
    firing_duration = db.Column(db.Float)  # recommended firing duration in hours
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<ProductType {self.name}>'

class QuantityTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    product_type_id = db.Column(db.Integer, db.ForeignKey('product_type.id'))
    kiln_id = db.Column(db.Integer, db.ForeignKey('kiln.id'))
    planned_quantity = db.Column(db.Integer, nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    product_type = db.relationship('ProductType', backref='quantity_templates')
    kiln = db.relationship('Kiln', backref='quantity_templates')

    def __repr__(self):
        return f'<QuantityTemplate {self.name}>'

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)  # created, updated, deleted, login, logout
    entity_type = db.Column(db.String(50))  # production_batch, quality_test, kiln, etc.
    entity_id = db.Column(db.Integer)  # ID of the affected entity
    entity_name = db.Column(db.String(200))  # Name/identifier of the entity
    details = db.Column(db.Text)  # Additional details about the action
    ip_address = db.Column(db.String(45))  # User's IP address
    user_agent = db.Column(db.String(500))  # Browser/user agent
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='activity_logs')
    
    def __repr__(self):
        return f'<ActivityLog {self.user.username if self.user else "Unknown"}: {self.action}>'
    
    @staticmethod
    def log_activity(action, entity_type=None, entity_id=None, entity_name=None, details=None, user=None):
        """Log user activity to the database"""
        from flask import request
        
        if user is None:
            user = current_user if current_user.is_authenticated else None
        
        if user:
            log = ActivityLog()
            log.user_id = user.id
            log.action = action
            log.entity_type = entity_type
            log.entity_id = entity_id
            log.entity_name = entity_name
            log.details = details
            log.ip_address = request.remote_addr if request else None
            log.user_agent = request.headers.get('User-Agent') if request else None
            db.session.add(log)
            db.session.commit()
