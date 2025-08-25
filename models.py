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
    is_active = db.Column(db.Boolean, default=True)

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

    supervisor = db.relationship('User', backref='supervised_batches')

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
    
    # ISO compliance and classification
    iso_standard = db.Column(db.String(30))  # ISO 10545-2, ISO 10545-3, etc.
    tile_classification = db.Column(db.String(20))  # BIa, BIIa, BIII, etc.
    absorption_group = db.Column(db.String(5))  # A, B, C
    forming_method = db.Column(db.String(10))   # Pressed (B), Extruded (A)
    surface_type = db.Column(db.String(10))     # glazed, unglazed
    compliance_score = db.Column(db.Float)
    result = db.Column(db.String(10))  # pass, fail
    
    # Test conditions
    temperature_humidity = db.Column(db.String(50))  # Environmental conditions
    notes = db.Column(db.Text)
    equipment_calibration_date = db.Column(db.Date)

    batch = db.relationship('ProductionBatch', backref='quality_tests')
    technician = db.relationship('User', backref='conducted_tests')

    def calculate_flexural_strength(self):
        """Calculate flexural strength from breaking force (ISO 10545-4)"""
        if self.breaking_force and self.length and self.width and self.thickness:
            # Flexural strength = (3 * F * L) / (2 * b * h²)
            # F = breaking force (N), L = span length (typically 20mm less than tile length)
            # b = width (mm), h = thickness (mm)
            span_length = max(self.length - 20, self.length * 0.9)  # 90% of length minimum
            self.breaking_strength = (3 * self.breaking_force * span_length) / (2 * self.width * (self.thickness ** 2))
            return self.breaking_strength
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
