from datetime import datetime
from app import db
from flask_login import UserMixin
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
    test_type = db.Column(db.String(50), nullable=False)  # dimensional, water_absorption, breaking_strength, abrasion
    test_date = db.Column(db.DateTime, default=datetime.utcnow)
    technician_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Dimensional measurements
    length = db.Column(db.Float)
    width = db.Column(db.Float)
    thickness = db.Column(db.Float)
    warping = db.Column(db.Float)
    
    # Physical properties
    water_absorption = db.Column(db.Float)
    breaking_strength = db.Column(db.Float)
    abrasion_resistance = db.Column(db.String(10))  # PEI class
    
    # Visual inspection
    visual_defects = db.Column(db.Text)
    
    # ISO compliance
    iso_standard = db.Column(db.String(20))  # ISO 13006, ISO 10545-3, etc.
    compliance_score = db.Column(db.Float)
    result = db.Column(db.String(10))  # pass, fail
    
    notes = db.Column(db.Text)
    equipment_calibration_date = db.Column(db.Date)

    batch = db.relationship('ProductionBatch', backref='quality_tests')
    technician = db.relationship('User', backref='conducted_tests')

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
    standard_code = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    min_threshold = db.Column(db.Float)
    max_threshold = db.Column(db.Float)
    unit = db.Column(db.String(20))
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<ISOStandard {self.standard_code}>'

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
