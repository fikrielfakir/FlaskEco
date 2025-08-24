#!/usr/bin/env python3
"""
EcoQuality Database Initialization Script
Initializes the database with sample data for testing and demonstration.
"""

import os
import sys
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import (
    User, ProductionBatch, QualityTest, EnergyConsumption, 
    WasteRecord, RawMaterial, ISOStandard
)

def init_database():
    """Initialize the database with tables and sample data."""
    
    with app.app_context():
        print("🔄 Initializing EcoQuality database...")
        
        # Create all tables
        db.create_all()
        print("✅ Database tables created successfully")
        
        # Check if data already exists
        if User.query.first():
            print("⚠️  Database already contains data. Skipping initialization.")
            return
        
        # Create users
        create_users()
        print("✅ Users created")
        
        # Create ISO standards
        create_iso_standards()
        print("✅ ISO standards created")
        
        # Create raw materials
        create_raw_materials()
        print("✅ Raw materials created")
        
        # Create production batches
        create_production_batches()
        print("✅ Production batches created")
        
        # Create quality tests
        create_quality_tests()
        print("✅ Quality tests created")
        
        # Create energy consumption records
        create_energy_records()
        print("✅ Energy consumption records created")
        
        # Create waste records
        create_waste_records()
        print("✅ Waste management records created")
        
        db.session.commit()
        print("🎉 Database initialization completed successfully!")
        print("\n📋 Login credentials:")
        print("   Admin: admin / admin123")
        print("   Quality Technician: tech1 / tech123")
        print("   Production Manager: prod1 / prod123")
        print("   Environment Manager: env1 / env123")
        print("   Operator: op1 / op123")

def create_users():
    """Create sample users with different roles."""
    
    users_data = [
        {
            'username': 'admin',
            'email': 'admin@ecoquality.ma',
            'password': 'admin123',
            'role': 'Admin'
        },
        {
            'username': 'tech1',
            'email': 'technicien@ecoquality.ma',
            'password': 'tech123',
            'role': 'Quality Technician'
        },
        {
            'username': 'prod1',
            'email': 'production@ecoquality.ma',
            'password': 'prod123',
            'role': 'Production Manager'
        },
        {
            'username': 'env1',
            'email': 'environnement@ecoquality.ma',
            'password': 'env123',
            'role': 'Environment Manager'
        },
        {
            'username': 'op1',
            'email': 'operateur@ecoquality.ma',
            'password': 'op123',
            'role': 'Operator'
        }
    ]
    
    for user_data in users_data:
        user = User(
            username=user_data['username'],
            email=user_data['email'],
            role=user_data['role']
        )
        user.set_password(user_data['password'])
        db.session.add(user)

def create_iso_standards():
    """Create ISO standards reference data."""
    
    standards = [
        {
            'standard_code': 'ISO 13006',
            'title': 'Carreaux et dalles céramiques - Définitions, classification, caractéristiques et marquage',
            'category': 'Classification',
            'description': 'Norme principale pour la classification des carreaux céramiques'
        },
        {
            'standard_code': 'ISO 10545-3',
            'title': 'Carreaux et dalles céramiques - Détermination de l\'absorption d\'eau',
            'category': 'Physical Properties',
            'min_threshold': 0.0,
            'max_threshold': 20.0,
            'unit': '%',
            'description': 'Méthode d\'essai pour déterminer l\'absorption d\'eau'
        },
        {
            'standard_code': 'ISO 10545-4',
            'title': 'Carreaux et dalles céramiques - Détermination de la résistance à la rupture',
            'category': 'Mechanical Properties',
            'min_threshold': 600.0,
            'unit': 'N',
            'description': 'Méthode d\'essai pour la résistance à la flexion'
        },
        {
            'standard_code': 'ISO 10545-7',
            'title': 'Carreaux et dalles céramiques - Détermination de la résistance à l\'abrasion',
            'category': 'Surface Properties',
            'description': 'Classification PEI pour la résistance à l\'abrasion'
        },
        {
            'standard_code': 'NM 10.1.008',
            'title': 'Carreaux céramiques - Spécifications marocaines',
            'category': 'National Standards',
            'description': 'Normes marocaines pour les carreaux céramiques'
        }
    ]
    
    for standard_data in standards:
        standard = ISOStandard(**standard_data)
        db.session.add(standard)

def create_raw_materials():
    """Create sample raw materials inventory."""
    
    # Get admin user for recording
    admin_user = User.query.filter_by(username='admin').first()
    
    materials = [
        {
            'name': 'Argile Rouge de Salé',
            'supplier': 'Carrières du Nord',
            'category': 'Argiles',
            'quantity_kg': 5000.0,
            'unit_cost': 45.50,
            'quality_grade': 'A',
            'date_received': date.today() - timedelta(days=15),
            'lot_number': 'ARG-202501-001',
            'specifications': 'Argile plastique, taux de fer 8-12%, granulométrie < 2mm',
            'quality_certified': True,
            'recorded_by_id': admin_user.id
        },
        {
            'name': 'Kaolin de Mohammedia',
            'supplier': 'Mines Atlas',
            'category': 'Kaolin',
            'quantity_kg': 2500.0,
            'unit_cost': 120.00,
            'quality_grade': 'A+',
            'date_received': date.today() - timedelta(days=10),
            'expiry_date': date.today() + timedelta(days=365),
            'lot_number': 'KAO-202501-001',
            'specifications': 'Kaolin pur, blancheur >85%, Al2O3 >38%',
            'quality_certified': True,
            'recorded_by_id': admin_user.id
        },
        {
            'name': 'Feldspath Potassique',
            'supplier': 'Minéraux du Maroc',
            'category': 'Feldspaths',
            'quantity_kg': 3000.0,
            'unit_cost': 78.00,
            'quality_grade': 'A',
            'date_received': date.today() - timedelta(days=8),
            'lot_number': 'FEL-202501-001',
            'specifications': 'K2O >10%, Na2O <3%, point de fusion 1150°C',
            'quality_certified': True,
            'recorded_by_id': admin_user.id
        },
        {
            'name': 'Quartz Broyé',
            'supplier': 'Sables Industriels',
            'category': 'Quartz',
            'quantity_kg': 4000.0,
            'unit_cost': 35.00,
            'quality_grade': 'A',
            'date_received': date.today() - timedelta(days=12),
            'lot_number': 'QUA-202501-001',
            'specifications': 'SiO2 >98%, granulométrie 0.1-0.5mm',
            'quality_certified': True,
            'recorded_by_id': admin_user.id
        },
        {
            'name': 'Chamotte 40%',
            'supplier': 'Recyclage Céramique',
            'category': 'Chamotte',
            'quantity_kg': 1500.0,
            'unit_cost': 25.00,
            'quality_grade': 'B',
            'date_received': date.today() - timedelta(days=5),
            'lot_number': 'CHA-202501-001',
            'specifications': 'Chamotte recyclée, taux d\'absorption <5%',
            'quality_certified': False,
            'recorded_by_id': admin_user.id
        }
    ]
    
    for material_data in materials:
        material = RawMaterial(**material_data)
        db.session.add(material)

def create_production_batches():
    """Create sample production batches."""
    
    # Get users
    admin_user = User.query.filter_by(username='admin').first()
    prod_user = User.query.filter_by(username='prod1').first()
    
    batches = [
        {
            'lot_number': 'LOT20250124001',
            'product_type': 'Carreaux Sol 30x30',
            'planned_quantity': 1000,
            'actual_quantity': 980,
            'production_date': date.today() - timedelta(days=5),
            'kiln_number': 'FOUR-001',
            'kiln_temperature': 1180.0,
            'firing_duration': 12.5,
            'status': 'completed',
            'supervisor_id': prod_user.id,
            'notes': 'Production normale, léger écart de quantité due au contrôle qualité'
        },
        {
            'lot_number': 'LOT20250124002',
            'product_type': 'Carreaux Mur 25x40',
            'planned_quantity': 800,
            'actual_quantity': 800,
            'production_date': date.today() - timedelta(days=4),
            'kiln_number': 'FOUR-002',
            'kiln_temperature': 1150.0,
            'firing_duration': 11.0,
            'status': 'approved',
            'supervisor_id': prod_user.id,
            'notes': 'Production conforme aux spécifications'
        },
        {
            'lot_number': 'LOT20250124003',
            'product_type': 'Grès Cérame 60x60',
            'planned_quantity': 500,
            'actual_quantity': 450,
            'production_date': date.today() - timedelta(days=3),
            'kiln_number': 'FOUR-001',
            'kiln_temperature': 1200.0,
            'firing_duration': 14.0,
            'status': 'completed',
            'supervisor_id': admin_user.id,
            'notes': 'Quelques pièces écartées pour défauts visuels mineurs'
        },
        {
            'lot_number': 'LOT20250124004',
            'product_type': 'Carreaux Sol 45x45',
            'planned_quantity': 750,
            'actual_quantity': 0,
            'production_date': date.today() - timedelta(days=1),
            'kiln_number': 'FOUR-003',
            'kiln_temperature': 1175.0,
            'firing_duration': 13.0,
            'status': 'in_progress',
            'supervisor_id': prod_user.id,
            'notes': 'Production en cours'
        },
        {
            'lot_number': 'LOT20250124005',
            'product_type': 'Carreaux Mur 20x25',
            'planned_quantity': 1200,
            'actual_quantity': 0,
            'production_date': date.today(),
            'kiln_number': 'FOUR-002',
            'status': 'planned',
            'supervisor_id': prod_user.id,
            'notes': 'Planifié pour aujourd\'hui'
        }
    ]
    
    for batch_data in batches:
        batch = ProductionBatch(**batch_data)
        db.session.add(batch)

def create_quality_tests():
    """Create sample quality test records."""
    
    # Get technician user
    tech_user = User.query.filter_by(username='tech1').first()
    
    # Get completed batches
    completed_batches = ProductionBatch.query.filter(
        ProductionBatch.status.in_(['completed', 'approved'])
    ).all()
    
    test_templates = [
        {
            'test_type': 'dimensional',
            'iso_standard': 'ISO 13006',
            'length': 299.8,
            'width': 299.6,
            'thickness': 8.2,
            'warping': 0.3,
            'compliance_score': 95.5,
            'result': 'pass',
            'notes': 'Toutes les mesures dans les tolérances acceptables'
        },
        {
            'test_type': 'water_absorption',
            'iso_standard': 'ISO 10545-3',
            'water_absorption': 3.2,
            'compliance_score': 92.0,
            'result': 'pass',
            'notes': 'Absorption conforme pour carreaux du groupe BIIa'
        },
        {
            'test_type': 'breaking_strength',
            'iso_standard': 'ISO 10545-4',
            'breaking_strength': 1250.0,
            'compliance_score': 88.0,
            'result': 'pass',
            'notes': 'Résistance supérieure au minimum requis (600N)'
        },
        {
            'test_type': 'abrasion',
            'iso_standard': 'ISO 10545-7',
            'abrasion_resistance': 'PEI III',
            'compliance_score': 90.0,
            'result': 'pass',
            'notes': 'Classe PEI III appropriée pour usage résidentiel'
        }
    ]
    
    for i, batch in enumerate(completed_batches[:3]):  # Only first 3 batches
        for j, template in enumerate(test_templates):
            test = QualityTest(
                batch_id=batch.id,
                technician_id=tech_user.id,
                test_date=datetime.now() - timedelta(days=4-i, hours=j),
                equipment_calibration_date=date.today() - timedelta(days=30),
                **template
            )
            db.session.add(test)

def create_energy_records():
    """Create sample energy consumption records."""
    
    # Get environment manager
    env_user = User.query.filter_by(username='env1').first()
    
    # Create records for the last 30 days
    for i in range(30):
        record_date = date.today() - timedelta(days=i)
        
        # Electricity consumption
        electricity_record = EnergyConsumption(
            date=record_date,
            energy_source='electricity',
            consumption_kwh=450.0 + (i % 10) * 20,  # Varying consumption
            cost=450.0 * 1.2,  # 1.2 MAD per kWh
            kiln_number=f'FOUR-{(i % 4) + 1:03d}',
            efficiency_rating=85.0 + (i % 10),
            heat_recovery_kwh=45.0 + (i % 5) * 10,
            recorded_by_id=env_user.id,
            notes=f'Consommation normale pour FOUR-{(i % 4) + 1:03d}'
        )
        db.session.add(electricity_record)
        
        # Gas consumption (every other day)
        if i % 2 == 0:
            gas_record = EnergyConsumption(
                date=record_date,
                energy_source='gas',
                consumption_kwh=300.0 + (i % 8) * 15,
                cost=300.0 * 0.8,  # 0.8 MAD per kWh equivalent
                kiln_number=f'FOUR-{(i % 4) + 1:03d}',
                efficiency_rating=78.0 + (i % 8),
                heat_recovery_kwh=30.0 + (i % 3) * 8,
                recorded_by_id=env_user.id,
                notes='Appoint gaz pour montée en température'
            )
            db.session.add(gas_record)
        
        # Solar energy (sunny days only)
        if i % 3 == 0:
            solar_record = EnergyConsumption(
                date=record_date,
                energy_source='solar',
                consumption_kwh=150.0 + (i % 6) * 25,
                cost=0.0,  # Solar is free
                efficiency_rating=92.0 + (i % 5),
                recorded_by_id=env_user.id,
                notes='Énergie solaire pour préchauffage'
            )
            db.session.add(solar_record)

def create_waste_records():
    """Create sample waste management records."""
    
    # Get environment manager
    env_user = User.query.filter_by(username='env1').first()
    
    waste_data = [
        {
            'date': date.today() - timedelta(days=7),
            'waste_type': 'liquid',
            'category': 'Eau de process',
            'quantity_kg': 1200.0,
            'disposal_method': 'recycled',
            'recycling_percentage': 100.0,
            'environmental_impact': 'Traitement par filtration et réutilisation dans le process',
            'notes': 'Système de recyclage en circuit fermé'
        },
        {
            'date': date.today() - timedelta(days=6),
            'waste_type': 'solid',
            'category': 'Rebuts céramiques',
            'quantity_kg': 450.0,
            'disposal_method': 'reused',
            'recycling_percentage': 100.0,
            'environmental_impact': 'Broyage et réintégration comme chamotte',
            'notes': 'Rebuts de qualité transformés en chamotte 30%'
        },
        {
            'date': date.today() - timedelta(days=5),
            'waste_type': 'liquid',
            'category': 'Eau de refroidissement',
            'quantity_kg': 800.0,
            'disposal_method': 'recycled',
            'recycling_percentage': 95.0,
            'environmental_impact': 'Refroidissement et recirculation',
            'notes': '5% de perte par évaporation'
        },
        {
            'date': date.today() - timedelta(days=4),
            'waste_type': 'solid',
            'category': 'Poussières',
            'quantity_kg': 120.0,
            'disposal_method': 'recycled',
            'recycling_percentage': 80.0,
            'environmental_impact': 'Récupération par dépoussiérage et réutilisation',
            'notes': 'Système de filtration efficace'
        },
        {
            'date': date.today() - timedelta(days=3),
            'waste_type': 'solid',
            'category': 'Emballages',
            'quantity_kg': 85.0,
            'disposal_method': 'recycled',
            'recycling_percentage': 100.0,
            'environmental_impact': 'Tri sélectif et envoi en filière de recyclage',
            'notes': 'Partenariat avec centre de tri local'
        },
        {
            'date': date.today() - timedelta(days=2),
            'waste_type': 'liquid',
            'category': 'Huiles usagées',
            'quantity_kg': 45.0,
            'disposal_method': 'recycled',
            'recycling_percentage': 100.0,
            'environmental_impact': 'Collection par entreprise spécialisée',
            'notes': 'Huiles hydrauliques et de maintenance'
        },
        {
            'date': date.today() - timedelta(days=1),
            'waste_type': 'solid',
            'category': 'Métaux',
            'quantity_kg': 65.0,
            'disposal_method': 'recycled',
            'recycling_percentage': 100.0,
            'environmental_impact': 'Récupération ferraille et métaux non ferreux',
            'notes': 'Maintenance équipements et structures'
        }
    ]
    
    for waste_info in waste_data:
        waste_record = WasteRecord(
            recorded_by_id=env_user.id,
            **waste_info
        )
        db.session.add(waste_record)

if __name__ == '__main__':
    init_database()
