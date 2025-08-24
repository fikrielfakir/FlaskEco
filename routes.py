from datetime import datetime, date
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from app import app, db
from models import User, ProductionBatch, QualityTest, EnergyConsumption, WasteRecord, RawMaterial, ISOStandard, Kiln, ProductType, QuantityTemplate, ActivityLog

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
            ActivityLog.log_activity('login', details=f'Successful login from {request.remote_addr}')
            flash('Connexion réussie!', 'success')
            return redirect(url_for('dashboard'))
        else:
            ActivityLog.log_activity('login_failed', details=f'Failed login attempt for username: {username} from {request.remote_addr}', user=user)
            flash('Nom d\'utilisateur ou mot de passe incorrect.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    ActivityLog.log_activity('logout', details=f'User logged out from {request.remote_addr}')
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
        ActivityLog.log_activity('created', 'production_batch', batch.id, lot_number, f'Created production batch: {batch.product_type}, {batch.planned_quantity} units')
        flash(f'Lot de production {lot_number} créé avec succès!', 'success')
        return redirect(url_for('production_index'))
    
    # Fetch kilns and product types from configuration
    kilns = Kiln.query.filter_by(is_active=True, status='active').order_by(Kiln.name).all()
    product_types = ProductType.query.filter_by(is_active=True).order_by(ProductType.name).all()
    quantity_templates = QuantityTemplate.query.filter_by(is_active=True).order_by(QuantityTemplate.name).all()
    
    return render_template('production/create_batch.html', kilns=kilns, product_types=product_types, quantity_templates=quantity_templates)

@app.route('/production/<int:batch_id>')
@login_required
def view_batch(batch_id):
    batch = ProductionBatch.query.get_or_404(batch_id)
    return render_template('production/view_batch.html', batch=batch)

@app.route('/production/<int:batch_id>/update_status', methods=['POST'])
@login_required
def update_batch_status(batch_id):
    new_status = request.form['status']
    actual_quantity = request.form.get('actual_quantity')
    
    batch = ProductionBatch.query.get_or_404(batch_id)
    old_status = batch.status
    batch.status = new_status
    batch.updated_at = datetime.utcnow()
    
    if actual_quantity:
        batch.actual_quantity = int(actual_quantity)
    
    db.session.commit()
    ActivityLog.log_activity('updated', 'production_batch', batch.id, batch.lot_number, f'Status changed from {old_status} to {new_status}')
    flash(f'Statut du lot {batch.lot_number} mis à jour: {new_status}', 'success')
    return redirect(url_for('view_batch', batch_id=batch_id))

@app.route('/production/<int:batch_id>/delete', methods=['POST'])
@login_required
def delete_batch(batch_id):
    batch = ProductionBatch.query.get_or_404(batch_id)
    lot_number = batch.lot_number
    
    # Log the deletion before removing
    ActivityLog.log_activity('deleted', 'production_batch', batch.id, lot_number, 
                           f'Deleted production batch: {batch.product_type}, {batch.planned_quantity} units')
    
    # Delete related quality tests first (cascade)
    QualityTest.query.filter_by(batch_id=batch.id).delete()
    
    # Delete the batch
    db.session.delete(batch)
    db.session.commit()
    
    flash(f'Lot de production {lot_number} supprimé avec succès!', 'success')
    return redirect(url_for('production_index'))

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
        
        # Try automatic result determination first
        auto_result = test.determine_result_automatically()
        if auto_result and not request.form.get('manual_override'):
            # Use automatic result
            test.result = auto_result
            ActivityLog.log_activity('created', 'quality_test', test.id, f"{test.test_type} test", 
                                   f'Test automatiquement évalué: {auto_result.upper()} (Score: {test.compliance_score:.1f}%)')
        else:
            # Use manual result if auto-detection failed or manual override requested
            test.compliance_score = float(request.form['compliance_score']) if request.form['compliance_score'] else None
            test.result = request.form['result']
            ActivityLog.log_activity('created', 'quality_test', test.id, f"{test.test_type} test", 
                                   f'Test manuellement évalué: {test.result.upper()}')
        
        db.session.add(test)
        db.session.commit()
        
        result_text = 'Conforme (Pass)' if test.result == 'pass' else 'Non Conforme (Fail)'
        flash(f'Test de qualité créé avec succès! Résultat: {result_text}', 'success' if test.result == 'pass' else 'warning')
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

# Configuration Management Routes
@app.route('/config')
@login_required
def config_index():
    return render_template('config/index.html')

@app.route('/activity-logs')
@login_required
def activity_logs():
    # Get all activity logs with pagination
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    activity_logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get all users for filter dropdown
    users = User.query.filter_by(is_active=True).order_by(User.username).all()
    
    return render_template('activity_logs.html', 
                         activity_logs=activity_logs.items, 
                         users=users,
                         pagination=activity_logs)

# Kiln Management Routes
@app.route('/config/kilns')
@login_required
def kilns_index():
    kilns = Kiln.query.filter_by(is_active=True).order_by(Kiln.name).all()
    return render_template('config/kilns/index.html', kilns=kilns)

@app.route('/config/kilns/create', methods=['GET', 'POST'])
@login_required
def create_kiln():
    if request.method == 'POST':
        kiln = Kiln(
            name=request.form['name'],
            max_temperature=float(request.form['max_temperature']),
            capacity=int(request.form['capacity']),
            status=request.form['status'],
            location=request.form['location'],
            installation_date=datetime.strptime(request.form['installation_date'], '%Y-%m-%d').date() if request.form['installation_date'] else None,
            last_maintenance=datetime.strptime(request.form['last_maintenance'], '%Y-%m-%d').date() if request.form['last_maintenance'] else None,
            notes=request.form['notes']
        )
        
        db.session.add(kiln)
        db.session.commit()
        ActivityLog.log_activity('created', 'kiln', kiln.id, kiln.name, f'Created kiln: {kiln.name}, capacity: {kiln.capacity}, max temp: {kiln.max_temperature}°C')
        flash(f'Four {kiln.name} créé avec succès!', 'success')
        return redirect(url_for('kilns_index'))
    
    return render_template('config/kilns/create.html')

@app.route('/config/kilns/<int:kiln_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_kiln(kiln_id):
    kiln = Kiln.query.get_or_404(kiln_id)
    
    if request.method == 'POST':
        kiln.name = request.form['name']
        kiln.max_temperature = float(request.form['max_temperature'])
        kiln.capacity = int(request.form['capacity'])
        kiln.status = request.form['status']
        kiln.location = request.form['location']
        kiln.installation_date = datetime.strptime(request.form['installation_date'], '%Y-%m-%d').date() if request.form['installation_date'] else None
        kiln.last_maintenance = datetime.strptime(request.form['last_maintenance'], '%Y-%m-%d').date() if request.form['last_maintenance'] else None
        kiln.notes = request.form['notes']
        
        db.session.commit()
        ActivityLog.log_activity('updated', 'kiln', kiln.id, kiln.name, f'Updated kiln: {kiln.name}')
        flash(f'Four {kiln.name} modifié avec succès!', 'success')
        return redirect(url_for('kilns_index'))
    
    return render_template('config/kilns/edit.html', kiln=kiln)

@app.route('/config/kilns/<int:kiln_id>/delete', methods=['POST'])
@login_required
def delete_kiln(kiln_id):
    kiln = Kiln.query.get_or_404(kiln_id)
    ActivityLog.log_activity('deleted', 'kiln', kiln.id, kiln.name, f'Deleted kiln: {kiln.name}')
    kiln.is_active = False
    db.session.commit()
    flash(f'Four {kiln.name} supprimé avec succès!', 'success')
    return redirect(url_for('kilns_index'))

# Product Type Management Routes
@app.route('/config/product-types')
@login_required
def product_types_index():
    product_types = ProductType.query.filter_by(is_active=True).order_by(ProductType.name).all()
    return render_template('config/product_types/index.html', product_types=product_types)

@app.route('/config/product-types/create', methods=['GET', 'POST'])
@login_required
def create_product_type():
    if request.method == 'POST':
        product_type = ProductType(
            name=request.form['name'],
            category=request.form['category'],
            dimensions=request.form['dimensions'],
            thickness=float(request.form['thickness']) if request.form['thickness'] else None,
            firing_temperature=float(request.form['firing_temperature']) if request.form['firing_temperature'] else None,
            firing_duration=float(request.form['firing_duration']) if request.form['firing_duration'] else None,
            description=request.form['description']
        )
        
        db.session.add(product_type)
        db.session.commit()
        flash(f'Type de produit {product_type.name} créé avec succès!', 'success')
        return redirect(url_for('product_types_index'))
    
    return render_template('config/product_types/create.html')

@app.route('/config/product-types/<int:product_type_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_product_type(product_type_id):
    product_type = ProductType.query.get_or_404(product_type_id)
    
    if request.method == 'POST':
        product_type.name = request.form['name']
        product_type.category = request.form['category']
        product_type.dimensions = request.form['dimensions']
        product_type.thickness = float(request.form['thickness']) if request.form['thickness'] else None
        product_type.firing_temperature = float(request.form['firing_temperature']) if request.form['firing_temperature'] else None
        product_type.firing_duration = float(request.form['firing_duration']) if request.form['firing_duration'] else None
        product_type.description = request.form['description']
        
        db.session.commit()
        flash(f'Type de produit {product_type.name} modifié avec succès!', 'success')
        return redirect(url_for('product_types_index'))
    
    return render_template('config/product_types/edit.html', product_type=product_type)

@app.route('/config/product-types/<int:product_type_id>/delete', methods=['POST'])
@login_required
def delete_product_type(product_type_id):
    product_type = ProductType.query.get_or_404(product_type_id)
    product_type.is_active = False
    db.session.commit()
    flash(f'Type de produit {product_type.name} supprimé avec succès!', 'success')
    return redirect(url_for('product_types_index'))

# Quantity Template Management Routes
@app.route('/config/quantities')
@login_required
def quantities_index():
    quantities = QuantityTemplate.query.filter_by(is_active=True).order_by(QuantityTemplate.name).all()
    return render_template('config/quantities/index.html', quantities=quantities)

@app.route('/config/quantities/create', methods=['GET', 'POST'])
@login_required
def create_quantity():
    if request.method == 'POST':
        quantity = QuantityTemplate(
            name=request.form['name'],
            product_type_id=int(request.form['product_type_id']) if request.form['product_type_id'] else None,
            kiln_id=int(request.form['kiln_id']) if request.form['kiln_id'] else None,
            planned_quantity=int(request.form['planned_quantity']),
            notes=request.form['notes']
        )
        
        db.session.add(quantity)
        db.session.commit()
        flash(f'Modèle de quantité {quantity.name} créé avec succès!', 'success')
        return redirect(url_for('quantities_index'))
    
    product_types = ProductType.query.filter_by(is_active=True).order_by(ProductType.name).all()
    kilns = Kiln.query.filter_by(is_active=True).order_by(Kiln.name).all()
    return render_template('config/quantities/create.html', product_types=product_types, kilns=kilns)

@app.route('/config/quantities/<int:quantity_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_quantity(quantity_id):
    quantity = QuantityTemplate.query.get_or_404(quantity_id)
    
    if request.method == 'POST':
        quantity.name = request.form['name']
        quantity.product_type_id = int(request.form['product_type_id']) if request.form['product_type_id'] else None
        quantity.kiln_id = int(request.form['kiln_id']) if request.form['kiln_id'] else None
        quantity.planned_quantity = int(request.form['planned_quantity'])
        quantity.notes = request.form['notes']
        
        db.session.commit()
        flash(f'Modèle de quantité {quantity.name} modifié avec succès!', 'success')
        return redirect(url_for('quantities_index'))
    
    product_types = ProductType.query.filter_by(is_active=True).order_by(ProductType.name).all()
    kilns = Kiln.query.filter_by(is_active=True).order_by(Kiln.name).all()
    return render_template('config/quantities/edit.html', quantity=quantity, product_types=product_types, kilns=kilns)

@app.route('/config/quantities/<int:quantity_id>/delete', methods=['POST'])
@login_required
def delete_quantity(quantity_id):
    quantity = QuantityTemplate.query.get_or_404(quantity_id)
    quantity.is_active = False
    db.session.commit()
    flash(f'Modèle de quantité {quantity.name} supprimé avec succès!', 'success')
    return redirect(url_for('quantities_index'))

# ISO Standards Management Routes
@app.route('/config/iso-standards')
@login_required
def iso_standards_index():
    search = request.args.get('search', '')
    test_type_filter = request.args.get('test_type', '')
    
    query = ISOStandard.query.filter_by(is_active=True)
    
    if search:
        query = query.filter(ISOStandard.standard_code.contains(search) | 
                           ISOStandard.title.contains(search))
    
    if test_type_filter:
        query = query.filter_by(test_type=test_type_filter)
    
    standards = query.order_by(ISOStandard.standard_code, ISOStandard.category).all()
    return render_template('config/iso_standards/index.html', 
                         standards=standards, 
                         search=search, 
                         test_type_filter=test_type_filter)

@app.route('/config/iso-standards/create', methods=['GET', 'POST'])
@login_required
def create_iso_standard():
    if request.method == 'POST':
        standard = ISOStandard(
            standard_code=request.form['standard_code'],
            title=request.form['title'],
            category=request.form['category'],
            test_type=request.form['test_type'],
            min_threshold=float(request.form['min_threshold']) if request.form['min_threshold'] else None,
            max_threshold=float(request.form['max_threshold']) if request.form['max_threshold'] else None,
            unit=request.form['unit'],
            description=request.form['description']
        )
        
        db.session.add(standard)
        db.session.commit()
        ActivityLog.log_activity('created', 'iso_standard', standard.id, f"{standard.standard_code}-{standard.category}", 
                               f'Created ISO standard: {standard.title}')
        flash(f'Norme ISO {standard.standard_code} créée avec succès!', 'success')
        return redirect(url_for('iso_standards_index'))
    
    return render_template('config/iso_standards/create.html')

@app.route('/config/iso-standards/<int:standard_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_iso_standard(standard_id):
    standard = ISOStandard.query.get_or_404(standard_id)
    
    if request.method == 'POST':
        standard.standard_code = request.form['standard_code']
        standard.title = request.form['title']
        standard.category = request.form['category']
        standard.test_type = request.form['test_type']
        standard.min_threshold = float(request.form['min_threshold']) if request.form['min_threshold'] else None
        standard.max_threshold = float(request.form['max_threshold']) if request.form['max_threshold'] else None
        standard.unit = request.form['unit']
        standard.description = request.form['description']
        
        db.session.commit()
        ActivityLog.log_activity('updated', 'iso_standard', standard.id, f"{standard.standard_code}-{standard.category}", 
                               f'Updated ISO standard: {standard.title}')
        flash(f'Norme ISO {standard.standard_code} modifiée avec succès!', 'success')
        return redirect(url_for('iso_standards_index'))
    
    return render_template('config/iso_standards/edit.html', standard=standard)

@app.route('/config/iso-standards/<int:standard_id>/delete', methods=['POST'])
@login_required
def delete_iso_standard(standard_id):
    standard = ISOStandard.query.get_or_404(standard_id)
    ActivityLog.log_activity('deleted', 'iso_standard', standard.id, f"{standard.standard_code}-{standard.category}", 
                           f'Deleted ISO standard: {standard.title}')
    standard.is_active = False
    db.session.commit()
    flash(f'Norme ISO {standard.standard_code} supprimée avec succès!', 'success')
    return redirect(url_for('iso_standards_index'))

@app.route('/config/iso-standards/init-defaults', methods=['POST'])
@login_required
def init_default_iso_standards():
    """Initialize database with default ISO standards from laboratory documents"""
    
    # Check if standards already exist
    existing_count = ISOStandard.query.count()
    if existing_count > 0:
        flash('Des normes ISO existent déjà dans le système.', 'info')
        return redirect(url_for('iso_standards_index'))
    
    # Create comprehensive ISO standards based on laboratory documents
    default_standards = [
        # Normes dimensionnelles selon ISO 10545-2
        ISOStandard(
            standard_code='ISO 10545-2',
            title='Tolérances dimensionnelles - Longueur ±0.5%',
            category='length',
            test_type='dimensional',
            min_threshold=None,  # Will be calculated as ±0.5% of nominal dimension
            max_threshold=None,  # Will be calculated as ±0.5% of nominal dimension
            unit='%',
            description='Tolérance dimensionnelle pour longueur selon ISO 10545-2: ±0.5%'
        ),
        ISOStandard(
            standard_code='ISO 10545-2',
            title='Tolérances dimensionnelles - Largeur ±0.5%',
            category='width',
            test_type='dimensional',
            min_threshold=None,
            max_threshold=None,
            unit='%',
            description='Tolérance dimensionnelle pour largeur selon ISO 10545-2: ±0.5%'
        ),
        ISOStandard(
            standard_code='ISO 10545-2',
            title='Tolérances dimensionnelles - Épaisseur ±1.5mm',
            category='thickness',
            test_type='dimensional',
            min_threshold=-1.5,
            max_threshold=1.5,
            unit='mm',
            description='Tolérance épaisseur selon ISO 10545-2: ±1.5mm'
        ),
        ISOStandard(
            standard_code='ISO 10545-2',
            title='Rectitude des arêtes - ±2mm',
            category='warping',
            test_type='dimensional',
            min_threshold=None,
            max_threshold=2.0,
            unit='mm',
            description='Rectitude des arêtes selon ISO 10545-2: ±2mm maximum'
        ),
        
        # Normes d'absorption d'eau selon NM ISO 13006
        ISOStandard(
            standard_code='NM ISO 13006',
            title='Absorption d\'eau - Groupe BIa (E ≤ 0.5%)',
            category='water_absorption',
            test_type='water_absorption',
            min_threshold=None,
            max_threshold=0.5,
            unit='%',
            description='Absorption d\'eau pour carreaux grès cérame BIa: E ≤ 0.5%'
        ),
        ISOStandard(
            standard_code='NM ISO 13006',
            title='Absorption d\'eau - Groupe BIb (0.5% < E ≤ 3%)',
            category='water_absorption',
            test_type='water_absorption',
            min_threshold=0.5,
            max_threshold=3.0,
            unit='%',
            description='Absorption d\'eau pour carreaux grès BIb: 0.5% < E ≤ 3%'
        ),
        ISOStandard(
            standard_code='NM ISO 13006',
            title='Absorption d\'eau - Groupe BIIa (3% < E ≤ 6%)',
            category='water_absorption',
            test_type='water_absorption',
            min_threshold=3.0,
            max_threshold=6.0,
            unit='%',
            description='Absorption d\'eau pour carreaux faïence BIIa: 3% < E ≤ 6%'
        ),
        ISOStandard(
            standard_code='NM ISO 13006',
            title='Absorption d\'eau - Groupe BIIb (6% < E ≤ 10%)',
            category='water_absorption',
            test_type='water_absorption',
            min_threshold=6.0,
            max_threshold=10.0,
            unit='%',
            description='Absorption d\'eau pour carreaux faïence BIIb: 6% < E ≤ 10%'
        ),
        ISOStandard(
            standard_code='NM ISO 13006',
            title='Absorption d\'eau - Groupe BIII (E > 10%)',
            category='water_absorption',
            test_type='water_absorption',
            min_threshold=10.0,
            max_threshold=None,
            unit='%',
            description='Absorption d\'eau pour carreaux terre cuite BIII: E > 10%'
        ),
        
        # Normes de résistance à la rupture selon NM ISO 13006
        ISOStandard(
            standard_code='NM ISO 13006',
            title='Résistance à la rupture - Groupe BIa',
            category='breaking_strength',
            test_type='breaking_strength',
            min_threshold=1300,
            max_threshold=None,
            unit='N',
            description='Force de rupture minimale pour carreaux BIa: ≥ 1300N (épaisseur ≥ 7.5mm)'
        ),
        ISOStandard(
            standard_code='NM ISO 13006',
            title='Résistance à la rupture - Groupe BIb',
            category='breaking_strength',
            test_type='breaking_strength',
            min_threshold=1100,
            max_threshold=None,
            unit='N',
            description='Force de rupture minimale pour carreaux BIb: ≥ 1100N (épaisseur ≥ 7.5mm)'
        ),
        ISOStandard(
            standard_code='NM ISO 13006',
            title='Résistance à la rupture - Groupe BIIa',
            category='breaking_strength',
            test_type='breaking_strength',
            min_threshold=1000,
            max_threshold=None,
            unit='N',
            description='Force de rupture minimale pour carreaux BIIa: ≥ 1000N (épaisseur ≥ 7.5mm)'
        ),
        ISOStandard(
            standard_code='NM ISO 13006',
            title='Résistance à la rupture - Groupe BIIb/BIII',
            category='breaking_strength',
            test_type='breaking_strength',
            min_threshold=600,
            max_threshold=None,
            unit='N',
            description='Force de rupture minimale pour carreaux BIIb/BIII: ≥ 600N (épaisseur ≥ 7.5mm)'
        ),
        
        # Normes de module de rupture selon NM ISO 13006  
        ISOStandard(
            standard_code='NM ISO 13006',
            title='Module de rupture - Groupe BIa',
            category='rupture_modulus',
            test_type='breaking_strength',
            min_threshold=35,
            max_threshold=None,
            unit='N/mm²',
            description='Module de rupture minimal pour carreaux BIa: ≥ 35 N/mm²'
        ),
        ISOStandard(
            standard_code='NM ISO 13006',
            title='Module de rupture - Groupe BIb',
            category='rupture_modulus',
            test_type='breaking_strength',
            min_threshold=30,
            max_threshold=None,
            unit='N/mm²',
            description='Module de rupture minimal pour carreaux BIb: ≥ 30 N/mm²'
        ),
        ISOStandard(
            standard_code='NM ISO 13006',
            title='Module de rupture - Groupe BIIa',
            category='rupture_modulus',
            test_type='breaking_strength',
            min_threshold=22,
            max_threshold=None,
            unit='N/mm²',
            description='Module de rupture minimal pour carreaux BIIa: ≥ 22 N/mm²'
        ),
        ISOStandard(
            standard_code='NM ISO 13006',
            title='Module de rupture - Groupe BIIb/BIII',
            category='rupture_modulus',
            test_type='breaking_strength',
            min_threshold=15,
            max_threshold=None,
            unit='N/mm²',
            description='Module de rupture minimal pour carreaux BIIb/BIII: ≥ 15 N/mm²'
        ),
    ]
    
    for standard in default_standards:
        db.session.add(standard)
    
    db.session.commit()
    ActivityLog.log_activity('created', 'iso_standards', None, 'Laboratory Standards', 
                           f'Initialized {len(default_standards)} ISO standards from laboratory documents')
    
    flash(f'{len(default_standards)} normes ISO extraites des documents laboratoire créées avec succès!', 'success')
    return redirect(url_for('iso_standards_index'))
