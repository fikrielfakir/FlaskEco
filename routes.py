from datetime import datetime, date
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from app import app, db
from models import User, ProductionBatch, QualityTest, EnergyConsumption, WasteRecord, RawMaterial, ISOStandard

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            flash('Connexion réussie!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Nom d\'utilisateur ou mot de passe incorrect.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Déconnexion réussie.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Get summary statistics
    total_batches = ProductionBatch.query.count()
    pending_batches = ProductionBatch.query.filter_by(status='in_progress').count()
    completed_tests = QualityTest.query.filter_by(result='pass').count()
    failed_tests = QualityTest.query.filter_by(result='fail').count()
    
    # Recent activity
    recent_batches = ProductionBatch.query.order_by(ProductionBatch.created_at.desc()).limit(5).all()
    recent_tests = QualityTest.query.order_by(QualityTest.test_date.desc()).limit(5).all()
    
    return render_template('dashboard.html', 
                         total_batches=total_batches,
                         pending_batches=pending_batches,
                         completed_tests=completed_tests,
                         failed_tests=failed_tests,
                         recent_batches=recent_batches,
                         recent_tests=recent_tests)

# Production Management Routes
@app.route('/production')
@login_required
def production_index():
    search = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    
    query = ProductionBatch.query
    
    if search:
        query = query.filter(ProductionBatch.lot_number.contains(search) | 
                           ProductionBatch.product_type.contains(search))
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    batches = query.order_by(ProductionBatch.created_at.desc()).all()
    return render_template('production/index.html', batches=batches, search=search, status_filter=status_filter)

@app.route('/production/create', methods=['GET', 'POST'])
@login_required
def create_batch():
    if request.method == 'POST':
        # Generate automatic lot number
        today = datetime.now()
        lot_prefix = f"LOT{today.strftime('%Y%m%d')}"
        last_batch = ProductionBatch.query.filter(ProductionBatch.lot_number.like(f"{lot_prefix}%")).order_by(ProductionBatch.id.desc()).first()
        
        if last_batch:
            last_num = int(last_batch.lot_number[-3:])
            lot_number = f"{lot_prefix}{str(last_num + 1).zfill(3)}"
        else:
            lot_number = f"{lot_prefix}001"
        
        batch = ProductionBatch(
            lot_number=lot_number,
            product_type=request.form['product_type'],
            planned_quantity=int(request.form['planned_quantity']),
            production_date=datetime.strptime(request.form['production_date'], '%Y-%m-%d').date(),
            kiln_number=request.form['kiln_number'],
            kiln_temperature=float(request.form['kiln_temperature']) if request.form['kiln_temperature'] else None,
            firing_duration=float(request.form['firing_duration']) if request.form['firing_duration'] else None,
            supervisor_id=current_user.id,
            notes=request.form['notes']
        )
        
        db.session.add(batch)
        db.session.commit()
        flash(f'Lot de production {lot_number} créé avec succès!', 'success')
        return redirect(url_for('production_index'))
    
    return render_template('production/create_batch.html')

@app.route('/production/<int:batch_id>')
@login_required
def view_batch(batch_id):
    batch = ProductionBatch.query.get_or_404(batch_id)
    return render_template('production/view_batch.html', batch=batch)

@app.route('/production/<int:batch_id>/update_status', methods=['POST'])
@login_required
def update_batch_status():
    batch_id = request.form['batch_id']
    new_status = request.form['status']
    actual_quantity = request.form.get('actual_quantity')
    
    batch = ProductionBatch.query.get_or_404(batch_id)
    batch.status = new_status
    batch.updated_at = datetime.utcnow()
    
    if actual_quantity:
        batch.actual_quantity = int(actual_quantity)
    
    db.session.commit()
    flash(f'Statut du lot {batch.lot_number} mis à jour: {new_status}', 'success')
    return redirect(url_for('view_batch', batch_id=batch_id))

# Quality Control Routes
@app.route('/quality')
@login_required
def quality_index():
    search = request.args.get('search', '')
    test_type = request.args.get('test_type', '')
    
    query = QualityTest.query.join(ProductionBatch)
    
    if search:
        query = query.filter(ProductionBatch.lot_number.contains(search))
    
    if test_type:
        query = query.filter_by(test_type=test_type)
    
    tests = query.order_by(QualityTest.test_date.desc()).all()
    return render_template('quality/index.html', tests=tests, search=search, test_type=test_type)

@app.route('/quality/create', methods=['GET', 'POST'])
@login_required
def create_test():
    if request.method == 'POST':
        test = QualityTest(
            batch_id=int(request.form['batch_id']),
            test_type=request.form['test_type'],
            technician_id=current_user.id,
            iso_standard=request.form['iso_standard'],
            notes=request.form['notes']
        )
        
        # Set measurements based on test type
        if request.form['test_type'] == 'dimensional':
            test.length = float(request.form['length']) if request.form['length'] else None
            test.width = float(request.form['width']) if request.form['width'] else None
            test.thickness = float(request.form['thickness']) if request.form['thickness'] else None
            test.warping = float(request.form['warping']) if request.form['warping'] else None
        elif request.form['test_type'] == 'water_absorption':
            test.water_absorption = float(request.form['water_absorption']) if request.form['water_absorption'] else None
        elif request.form['test_type'] == 'breaking_strength':
            test.breaking_strength = float(request.form['breaking_strength']) if request.form['breaking_strength'] else None
        elif request.form['test_type'] == 'abrasion':
            test.abrasion_resistance = request.form['abrasion_resistance']
        
        test.visual_defects = request.form['visual_defects']
        test.compliance_score = float(request.form['compliance_score']) if request.form['compliance_score'] else None
        test.result = request.form['result']
        
        db.session.add(test)
        db.session.commit()
        flash('Test de qualité créé avec succès!', 'success')
        return redirect(url_for('quality_index'))
    
    batches = ProductionBatch.query.filter_by(status='completed').all()
    return render_template('quality/create_test.html', batches=batches)

@app.route('/quality/<int:test_id>')
@login_required
def view_test(test_id):
    test = QualityTest.query.get_or_404(test_id)
    return render_template('quality/view_test.html', test=test)

# Energy Monitoring Routes
@app.route('/energy')
@login_required
def energy_index():
    records = EnergyConsumption.query.order_by(EnergyConsumption.date.desc()).all()
    return render_template('energy/index.html', records=records)

@app.route('/energy/add', methods=['GET', 'POST'])
@login_required
def add_energy_consumption():
    if request.method == 'POST':
        record = EnergyConsumption(
            date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(),
            energy_source=request.form['energy_source'],
            consumption_kwh=float(request.form['consumption_kwh']),
            cost=float(request.form['cost']) if request.form['cost'] else None,
            kiln_number=request.form['kiln_number'],
            efficiency_rating=float(request.form['efficiency_rating']) if request.form['efficiency_rating'] else None,
            heat_recovery_kwh=float(request.form['heat_recovery_kwh']) if request.form['heat_recovery_kwh'] else 0,
            recorded_by_id=current_user.id,
            notes=request.form['notes']
        )
        
        db.session.add(record)
        db.session.commit()
        flash('Consommation énergétique enregistrée avec succès!', 'success')
        return redirect(url_for('energy_index'))
    
    return render_template('energy/add_consumption.html')

# Waste Management Routes
@app.route('/waste')
@login_required
def waste_index():
    records = WasteRecord.query.order_by(WasteRecord.date.desc()).all()
    return render_template('waste/index.html', records=records)

@app.route('/waste/add', methods=['GET', 'POST'])
@login_required
def add_waste_record():
    if request.method == 'POST':
        record = WasteRecord(
            date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(),
            waste_type=request.form['waste_type'],
            category=request.form['category'],
            quantity_kg=float(request.form['quantity_kg']),
            disposal_method=request.form['disposal_method'],
            recycling_percentage=float(request.form['recycling_percentage']) if request.form['recycling_percentage'] else 0,
            environmental_impact=request.form['environmental_impact'],
            recorded_by_id=current_user.id,
            notes=request.form['notes']
        )
        
        db.session.add(record)
        db.session.commit()
        flash('Enregistrement de déchets ajouté avec succès!', 'success')
        return redirect(url_for('waste_index'))
    
    return render_template('waste/add_record.html')

# Raw Materials Routes
@app.route('/materials')
@login_required
def materials_index():
    search = request.args.get('search', '')
    
    query = RawMaterial.query
    
    if search:
        query = query.filter(RawMaterial.name.contains(search) | 
                           RawMaterial.supplier.contains(search))
    
    materials = query.order_by(RawMaterial.created_at.desc()).all()
    return render_template('materials/index.html', materials=materials, search=search)

@app.route('/materials/add', methods=['GET', 'POST'])
@login_required
def add_material():
    if request.method == 'POST':
        material = RawMaterial(
            name=request.form['name'],
            supplier=request.form['supplier'],
            category=request.form['category'],
            quantity_kg=float(request.form['quantity_kg']),
            unit_cost=float(request.form['unit_cost']) if request.form['unit_cost'] else None,
            quality_grade=request.form['quality_grade'],
            date_received=datetime.strptime(request.form['date_received'], '%Y-%m-%d').date(),
            expiry_date=datetime.strptime(request.form['expiry_date'], '%Y-%m-%d').date() if request.form['expiry_date'] else None,
            lot_number=request.form['lot_number'],
            specifications=request.form['specifications'],
            quality_certified='quality_certified' in request.form,
            recorded_by_id=current_user.id
        )
        
        db.session.add(material)
        db.session.commit()
        flash('Matière première ajoutée avec succès!', 'success')
        return redirect(url_for('materials_index'))
    
    return render_template('materials/add_material.html')
