from datetime import datetime, date
from flask import render_template, request, redirect, url_for, flash, jsonify, send_file, make_response
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from app import app, db
from models import User, ProductionBatch, QualityTest, EnergyConsumption, WasteRecord, RawMaterial, ISOStandard, Kiln, ProductType, QuantityTemplate, ActivityLog
import io
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.graphics.shapes import Drawing, Line
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

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
        
        batch = ProductionBatch()
        batch.lot_number = lot_number
        batch.product_type = request.form['product_type']
        batch.planned_quantity = int(request.form['planned_quantity'])
        batch.production_date = datetime.strptime(request.form['production_date'], '%Y-%m-%d').date()
        batch.kiln_number = request.form['kiln_number']
        batch.kiln_temperature = float(request.form['kiln_temperature']) if request.form['kiln_temperature'] else None
        batch.firing_duration = float(request.form['firing_duration']) if request.form['firing_duration'] else None
        batch.supervisor_id = current_user.id
        batch.notes = request.form['notes']
        
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
        # Generate sample ID automatically
        today = datetime.now()
        sample_prefix = f"SAMP{today.strftime('%Y%m%d')}"
        last_sample = QualityTest.query.filter(QualityTest.sample_id.like(f"{sample_prefix}%")).order_by(QualityTest.id.desc()).first()
        
        if last_sample and last_sample.sample_id:
            last_num = int(last_sample.sample_id[-3:])
            sample_id = f"{sample_prefix}{str(last_num + 1).zfill(3)}"
        else:
            sample_id = f"{sample_prefix}001"
        
        test = QualityTest()
        test.batch_id = int(request.form['batch_id'])
        test.test_type = request.form['test_type']
        test.technician_id = current_user.id
        test.sample_id = sample_id
        test.iso_standard = request.form['iso_standard']
        test.forming_method = request.form.get('forming_method', 'Pressed')
        test.surface_type = request.form.get('surface_type', 'glazed')
        test.temperature_humidity = request.form.get('temperature_humidity', '')
        test.notes = request.form['notes']
        
        # Set measurements based on test type
        if request.form['test_type'] == 'dimensional':
            test.length = float(request.form['length']) if request.form['length'] else None
            test.width = float(request.form['width']) if request.form['width'] else None
            test.thickness = float(request.form['thickness']) if request.form['thickness'] else None
            test.straightness = float(request.form['straightness']) if request.form['straightness'] else None
            test.flatness = float(request.form['flatness']) if request.form['flatness'] else None
            test.rectangularity = float(request.form['rectangularity']) if request.form['rectangularity'] else None
            test.warping = float(request.form['warping']) if request.form['warping'] else None
            
        elif request.form['test_type'] == 'water_absorption':
            test.water_absorption = float(request.form['water_absorption']) if request.form['water_absorption'] else None
            
        elif request.form['test_type'] == 'breaking_strength':
            test.breaking_force = float(request.form['breaking_force']) if request.form['breaking_force'] else None
            # Calculate flexural strength automatically if dimensions are available
            if test.breaking_force and request.form.get('auto_calculate_strength') == 'on':
                # Get dimensions from the form or previous tests
                test.length = float(request.form['tile_length']) if request.form['tile_length'] else None
                test.width = float(request.form['tile_width']) if request.form['tile_width'] else None  
                test.thickness = float(request.form['tile_thickness']) if request.form['tile_thickness'] else None
                test.calculate_flexural_strength()
            else:
                test.breaking_strength = float(request.form['breaking_strength']) if request.form['breaking_strength'] else None
                
        elif request.form['test_type'] == 'abrasion':
            test.abrasion_resistance = request.form['abrasion_resistance']
            test.abrasion_cycles = int(request.form['abrasion_cycles']) if request.form['abrasion_cycles'] else None
            test.volume_loss = float(request.form['volume_loss']) if request.form['volume_loss'] else None
            
        elif request.form['test_type'] == 'clay_testing':
            # Clay humidity tests at different stages
            test.clay_humidity_hopper = float(request.form['clay_humidity_hopper']) if request.form['clay_humidity_hopper'] else None
            test.clay_humidity_sieved = float(request.form['clay_humidity_sieved']) if request.form['clay_humidity_sieved'] else None
            test.clay_humidity_silo = float(request.form['clay_humidity_silo']) if request.form['clay_humidity_silo'] else None
            test.clay_humidity_press = float(request.form['clay_humidity_press']) if request.form['clay_humidity_press'] else None
            # Granulometry and carbonate testing
            test.clay_granulometry_refusal = float(request.form['clay_granulometry_refusal']) if request.form['clay_granulometry_refusal'] else None
            test.clay_carbonate_content = float(request.form['clay_carbonate_content']) if request.form['clay_carbonate_content'] else None
            
        elif request.form['test_type'] == 'thermal_shock':
            test.thermal_shock_resistance = request.form.get('thermal_shock_resistance') == 'on'
            test.shrinkage_expansion = float(request.form['shrinkage_expansion']) if request.form['shrinkage_expansion'] else None
            test.loss_on_ignition = float(request.form['loss_on_ignition']) if request.form['loss_on_ignition'] else None
            
        elif request.form['test_type'] == 'glaze_testing':
            test.glaze_density = float(request.form['glaze_density']) if request.form['glaze_density'] else None
            test.glaze_viscosity = float(request.form['glaze_viscosity']) if request.form['glaze_viscosity'] else None
            test.glaze_refusal = float(request.form['glaze_refusal']) if request.form['glaze_refusal'] else None
            
        elif request.form['test_type'] == 'cetemco_testing':
            test.thermal_resistance = request.form.get('thermal_resistance', '')
            test.chemical_resistance = request.form.get('chemical_resistance', '')
            test.stain_resistance = request.form.get('stain_resistance', '')
        
        test.visual_defects = request.form['visual_defects']
        
        # Try automatic result determination first
        auto_result = test.determine_result_automatically()
        if auto_result and not request.form.get('manual_override'):
            # Use automatic result
            test.result = auto_result
            classification_info = f" | Classification: {test.tile_classification}" if test.tile_classification else ""
            ActivityLog.log_activity('created', 'quality_test', test.id, f"{test.test_type} test", 
                                   f'Test automatiquement évalué: {auto_result.upper()} (Score: {test.compliance_score:.1f}%){classification_info}')
        else:
            # Use manual result if auto-detection failed or manual override requested
            test.compliance_score = float(request.form['compliance_score']) if request.form['compliance_score'] else None
            test.result = request.form['result']
            test.tile_classification = request.form.get('tile_classification', '')
            ActivityLog.log_activity('created', 'quality_test', test.id, f"{test.test_type} test", 
                                   f'Test manuellement évalué: {test.result.upper()}')
        
        db.session.add(test)
        db.session.commit()
        
        result_text = 'Conforme (Pass)' if test.result == 'pass' else 'Non Conforme (Fail)'
        classification_text = f" - Classification: {test.tile_classification}" if test.tile_classification else ""
        flash(f'Test de qualité créé avec succès! Échantillon: {sample_id} | Résultat: {result_text}{classification_text}', 
              'success' if test.result == 'pass' else 'warning')
        return redirect(url_for('quality_index'))
    
    batches = ProductionBatch.query.filter_by(status='completed').all()
    iso_standards = {
        'dimensional': 'ISO 10545-2',
        'water_absorption': 'ISO 10545-3', 
        'breaking_strength': 'ISO 10545-4',
        'abrasion': 'ISO 10545-6',
        'clay_testing': 'R2-MA-LABO-01',
        'thermal_shock': 'R2-MA-LABO-04',
        'glaze_testing': 'R2-MA-LABO-05',
        'cetemco_testing': 'ISO 10545-9/11/13/14'
    }
    return render_template('quality/create_test.html', batches=batches, iso_standards=iso_standards)

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

# Export Routes
@app.route('/quality/export/<format_type>')
@login_required
def export_quality_tests(format_type):
    """Export quality tests in PDF or Excel format"""
    # Get filters from query parameters
    search = request.args.get('search', '')
    test_type = request.args.get('test_type', '')
    
    query = QualityTest.query.join(ProductionBatch)
    
    if search:
        query = query.filter(ProductionBatch.lot_number.contains(search))
    
    if test_type:
        query = query.filter_by(test_type=test_type)
    
    tests = query.order_by(QualityTest.test_date.desc()).all()
    
    if format_type == 'pdf':
        return generate_quality_pdf_report(tests)
    elif format_type == 'excel':
        return generate_quality_excel_report(tests)
    else:
        flash('Format d\'export non supporté.', 'error')
        return redirect(url_for('quality_index'))

@app.route('/quality/<int:test_id>/export/<format_type>')
@login_required
def export_single_quality_test(test_id, format_type):
    """Export a single quality test as professional report"""
    test = QualityTest.query.get_or_404(test_id)
    
    if format_type == 'pdf':
        return generate_single_test_pdf_report(test)
    elif format_type == 'excel':
        return generate_single_test_excel_report(test)
    else:
        flash('Format d\'export non supporté.', 'error')
        return redirect(url_for('view_test', test_id=test_id))

@app.route('/production/export/<format_type>')
@login_required
def export_production_batches(format_type):
    """Export production batches in PDF or Excel format"""
    search = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    
    query = ProductionBatch.query
    
    if search:
        query = query.filter(ProductionBatch.lot_number.contains(search) | 
                           ProductionBatch.product_type.contains(search))
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    batches = query.order_by(ProductionBatch.created_at.desc()).all()
    
    if format_type == 'pdf':
        return generate_production_pdf_report(batches)
    elif format_type == 'excel':
        return generate_production_excel_report(batches)
    else:
        flash('Format d\'export non supporté.', 'error')
        return redirect(url_for('production_index'))

def generate_quality_pdf_report(tests):
    """Generate professional PDF report for quality tests"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    # Container for the 'Flowable' objects
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#2c3e50')
    )
    
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=20,
        textColor=colors.HexColor('#34495e')
    )
    
    # Title
    title = Paragraph("RAPPORT DE CONTRÔLE QUALITÉ", title_style)
    elements.append(title)
    
    # Company header
    company_info = Paragraph(
        f"<b>CERAMICA DERS</b><br/>"
        f"SERVICE LABORATOIRE<br/>"
        f"Date d'édition: {datetime.now().strftime('%d/%m/%Y')}<br/>"
        f"Nombre de tests: {len(tests)}",
        header_style
    )
    elements.append(company_info)
    elements.append(Spacer(1, 20))
    
    if tests:
        # Table data
        data = [['Date', 'N° Lot', 'Type Test', 'Norme ISO', 'Technicien', 'Score', 'Résultat']]
        
        for test in tests:
            score = f"{test.compliance_score:.1f}%" if test.compliance_score else "-"
            result_text = "Conforme" if test.result == 'pass' else "Non conforme"
            
            data.append([
                test.test_date.strftime('%d/%m/%Y'),
                test.batch.lot_number,
                test.test_type,
                test.iso_standard or '-',
                test.technician.username,
                score,
                result_text
            ])
        
        # Create table
        table = Table(data, colWidths=[1*inch, 1.2*inch, 1.1*inch, 1*inch, 1*inch, 0.8*inch, 1*inch])
        
        # Table style
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(table)
    else:
        no_data = Paragraph("Aucun test de qualité trouvé.", styles['Normal'])
        elements.append(no_data)
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f'rapport_qualite_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf',
        mimetype='application/pdf'
    )

@app.route('/quality/initialize-iso-standards', methods=['POST'])
@login_required
def initialize_iso_standards():
    """Initialize ISO 10545 and NM ISO 13006 standards"""
    default_standards = [
        # ISO 10545-2: Dimensional tests
        {
            'standard_code': 'ISO 10545-2',
            'title': 'Détermination des dimensions et de la qualité de surface',
            'category': 'length_tolerance',
            'test_type': 'dimensional',
            'min_threshold': -0.6,  # -0.6% for porcelain
            'max_threshold': 0.6,   # +0.6% for porcelain
            'unit': '%',
            'description': 'Tolérance dimensionnelle pour carreaux en porcelaine (BIa): ±0.6% max 2.0mm'
        },
        {
            'standard_code': 'ISO 10545-2',
            'title': 'Détermination des dimensions et de la qualité de surface',
            'category': 'thickness_tolerance',
            'test_type': 'dimensional',
            'min_threshold': -5.0,  # -5.0% for porcelain
            'max_threshold': 5.0,   # +5.0% for porcelain
            'unit': '%',
            'description': 'Tolérance d\'épaisseur pour carreaux en porcelaine (BIa): ±5.0%'
        },
        {
            'standard_code': 'ISO 10545-2',
            'title': 'Détermination des dimensions et de la qualité de surface',
            'category': 'straightness',
            'test_type': 'dimensional',
            'min_threshold': None,
            'max_threshold': 0.5,   # max 0.5%
            'unit': '%',
            'description': 'Rectitude maximale pour carreaux en porcelaine: ±0.5%'
        },
        {
            'standard_code': 'ISO 10545-2',
            'title': 'Détermination des dimensions et de la qualité de surface',
            'category': 'flatness',
            'test_type': 'dimensional',
            'min_threshold': None,
            'max_threshold': 0.5,   # max 0.5%
            'unit': '%',
            'description': 'Planéité maximale pour carreaux en porcelaine: ±0.5%'
        },
        # ISO 10545-3: Water absorption
        {
            'standard_code': 'ISO 10545-3',
            'title': 'Détermination de l\'absorption d\'eau',
            'category': 'water_absorption',
            'test_type': 'water_absorption',
            'min_threshold': None,
            'max_threshold': 0.5,   # ≤0.5% for porcelain (BIa)
            'unit': '%',
            'description': 'Absorption d\'eau pour carreaux en porcelaine (BIa): ≤0.5%'
        },
        {
            'standard_code': 'ISO 10545-3',
            'title': 'Détermination de l\'absorption d\'eau',
            'category': 'water_absorption',
            'test_type': 'water_absorption',
            'min_threshold': None,
            'max_threshold': 3.0,   # ≤3.0% for stoneware (BIIa)
            'unit': '%',
            'description': 'Absorption d\'eau pour carreaux en grès cérame (BIIa): 0.5% < E ≤ 3%'
        },
        # ISO 10545-4: Breaking strength
        {
            'standard_code': 'ISO 10545-4',
            'title': 'Détermination de la résistance à la rupture et de la force de rupture',
            'category': 'breaking_strength',
            'test_type': 'breaking_strength',
            'min_threshold': 35,    # ≥35 N/mm² for porcelain
            'max_threshold': None,
            'unit': 'N/mm²',
            'description': 'Résistance à la flexion pour carreaux en porcelaine (BIa): ≥35 N/mm²'
        },
        {
            'standard_code': 'ISO 10545-4',
            'title': 'Détermination de la résistance à la rupture et de la force de rupture',
            'category': 'breaking_force',
            'test_type': 'breaking_strength',
            'min_threshold': 1300,  # ≥1300 N for standard tiles
            'max_threshold': None,
            'unit': 'N',
            'description': 'Force de rupture minimale pour carreaux: ≥1300 N'
        },
        # ISO 10545-6: Abrasion resistance for glazed tiles
        {
            'standard_code': 'ISO 10545-6',
            'title': 'Détermination de la résistance à l\'abrasion profonde pour les carreaux non émaillés',
            'category': 'abrasion',
            'test_type': 'abrasion',
            'min_threshold': None,
            'max_threshold': None,
            'unit': 'PEI Class',
            'description': 'Classification PEI pour carreaux émaillés: PEI I à PEI V selon usage'
        },
        # NM ISO 13006: Moroccan national standard
        {
            'standard_code': 'NM ISO 13006',
            'title': 'Carreaux et dalles céramiques - Définitions, classification, caractéristiques et marquage',
            'category': 'classification',
            'test_type': 'water_absorption',
            'min_threshold': None,
            'max_threshold': None,
            'unit': 'Classification',
            'description': 'Norme marocaine basée sur ISO 13006 v2016 pour classification et marquage'
        }
    ]
    
    created_count = 0
    for std_data in default_standards:
        # Check if standard already exists
        existing = ISOStandard.query.filter_by(
            standard_code=std_data['standard_code'],
            category=std_data['category'],
            test_type=std_data['test_type']
        ).first()
        
        if not existing:
            standard = ISOStandard(**std_data)
            db.session.add(standard)
            created_count += 1
    
    db.session.commit()
    ActivityLog.log_activity('created', 'iso_standards', None, 'ISO 10545 series', 
                           f'Initialized {created_count} ISO standards for ceramic tile testing')
    
    flash(f'{created_count} normes ISO 10545 et NM ISO 13006 initialisées avec succès!', 'success')
    return redirect(url_for('quality_index'))

def generate_single_test_pdf_report(test):
    """Generate professional PDF report for a single quality test"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=20,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#2c3e50')
    )
    
    # Title based on test type
    if test.test_type == 'dimensional':
        title_text = "RÉSULTATS DES ESSAIS DIMENSIONNELS ET QUALITÉ DE SURFACE"
    elif test.test_type == 'water_absorption':
        title_text = "CONTRÔLE D'ABSORPTION D'EAU"
    elif test.test_type == 'breaking_strength':
        title_text = "CONTRÔLE DE RÉSISTANCE"
    else:
        title_text = "RAPPORT DE TEST DE QUALITÉ"
    
    title = Paragraph(title_text, title_style)
    elements.append(title)
    
    # Header with company info
    header_data = [
        ['CERAMICA DERS', 'SERVICE LABORATOIRE'],
        ['CODE:', f'EQ-{test.test_type.upper()}-{test.id:04d}'],
        ['VERSION:', '2.0'],
        ['DATE:', test.test_date.strftime('%d/%m/%Y')]
    ]
    
    header_table = Table(header_data, colWidths=[3*inch, 3*inch])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ecf0f1')),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT')
    ]))
    
    elements.append(header_table)
    elements.append(Spacer(1, 20))
    
    # Technical data section
    tech_data = [
        ['Données techniques:', '', 'Date:', test.test_date.strftime('%d/%m/%Y')],
        ['Numéro de lot:', test.batch.lot_number, 'Type de produit:', test.batch.product_type],
        ['Norme ISO:', test.iso_standard or 'N/A', 'Technicien:', test.technician.username]
    ]
    
    tech_table = Table(tech_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
    tech_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#ecf0f1'))
    ]))
    
    elements.append(tech_table)
    elements.append(Spacer(1, 20))
    
    # Measurements table based on test type
    if test.test_type == 'dimensional':
        measurement_data = [
            ['Paramètre', 'Valeur mesurée', 'Unité', 'Spécification', 'Résultat'],
            ['Longueur', f'{test.length:.2f}' if test.length else 'N/A', 'mm', 'ISO 13006', '✓' if test.result == 'pass' else '✗'],
            ['Largeur', f'{test.width:.2f}' if test.width else 'N/A', 'mm', 'ISO 13006', '✓' if test.result == 'pass' else '✗'],
            ['Épaisseur', f'{test.thickness:.2f}' if test.thickness else 'N/A', 'mm', 'ISO 13006', '✓' if test.result == 'pass' else '✗'],
            ['Gauchissement', f'{test.warping:.2f}' if test.warping else 'N/A', 'mm', '< 0.5%', '✓' if test.result == 'pass' else '✗']
        ]
    elif test.test_type == 'water_absorption':
        measurement_data = [
            ['Paramètre', 'Valeur mesurée', 'Unité', 'Spécification', 'Résultat'],
            ['Absorption d\'eau', f'{test.water_absorption:.2f}' if test.water_absorption else 'N/A', '%', '< 3%', '✓' if test.result == 'pass' else '✗']
        ]
    elif test.test_type == 'breaking_strength':
        measurement_data = [
            ['Paramètre', 'Valeur mesurée', 'Unité', 'Spécification', 'Résultat'],
            ['Résistance à la rupture', f'{test.breaking_strength:.2f}' if test.breaking_strength else 'N/A', 'N/mm²', '> 1300 N', '✓' if test.result == 'pass' else '✗']
        ]
    else:
        measurement_data = [
            ['Paramètre', 'Valeur mesurée', 'Unité', 'Spécification', 'Résultat'],
            ['Test générique', 'Voir notes', '-', test.iso_standard or 'N/A', '✓' if test.result == 'pass' else '✗']
        ]
    
    measurement_table = Table(measurement_data, colWidths=[1.5*inch, 1.2*inch, 0.8*inch, 1.2*inch, 1*inch])
    measurement_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER')
    ]))
    
    elements.append(measurement_table)
    elements.append(Spacer(1, 20))
    
    # Final result section
    result_text = "CONFORME" if test.result == 'pass' else "NON CONFORME"
    result_color = colors.green if test.result == 'pass' else colors.red
    
    result_style = ParagraphStyle(
        'ResultStyle',
        parent=styles['Normal'],
        fontSize=14,
        textColor=result_color,
        alignment=TA_CENTER,
        spaceAfter=20
    )
    
    elements.append(Paragraph(f"<b>RÉSULTAT: {result_text}</b>", result_style))
    
    if test.compliance_score:
        elements.append(Paragraph(f"Score de conformité: {test.compliance_score:.1f}%", styles['Normal']))
    
    if test.notes:
        elements.append(Spacer(1, 10))
        elements.append(Paragraph("<b>Notes:</b>", styles['Normal']))
        elements.append(Paragraph(test.notes, styles['Normal']))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f'test_{test.test_type}_{test.batch.lot_number}_{test.test_date.strftime("%Y%m%d")}.pdf',
        mimetype='application/pdf'
    )

def generate_quality_excel_report(tests):
    """Generate Excel report for quality tests"""
    # Create a DataFrame
    data = []
    for test in tests:
        data.append({
            'Date': test.test_date.strftime('%d/%m/%Y'),
            'Numéro de Lot': test.batch.lot_number,
            'Type de Produit': test.batch.product_type,
            'Type de Test': test.test_type,
            'Norme ISO': test.iso_standard or '',
            'Technicien': test.technician.username,
            'Longueur (mm)': test.length if test.length else '',
            'Largeur (mm)': test.width if test.width else '',
            'Épaisseur (mm)': test.thickness if test.thickness else '',
            'Gauchissement (mm)': test.warping if test.warping else '',
            'Absorption d\'eau (%)': test.water_absorption if test.water_absorption else '',
            'Résistance rupture (N/mm²)': test.breaking_strength if test.breaking_strength else '',
            'Résistance abrasion': test.abrasion_resistance if test.abrasion_resistance else '',
            'Score de Conformité (%)': test.compliance_score if test.compliance_score else '',
            'Résultat': 'Conforme' if test.result == 'pass' else 'Non conforme',
            'Défauts visuels': test.visual_defects if test.visual_defects else '',
            'Notes': test.notes if test.notes else ''
        })
    
    df = pd.DataFrame(data)
    
    # Create Excel file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Tests de Qualité', index=False)
        
        # Get the workbook and worksheet
        workbook = writer.book
        worksheet = writer.sheets['Tests de Qualité']
        
        # Auto-adjust column widths
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    output.seek(0)
    
    return send_file(
        output,
        as_attachment=True,
        download_name=f'rapport_qualite_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

def generate_single_test_excel_report(test):
    """Generate Excel report for a single quality test"""
    # Basic test info
    data = [{
        'Numéro de Lot': test.batch.lot_number,
        'Type de Produit': test.batch.product_type,
        'Date de Test': test.test_date.strftime('%d/%m/%Y'),
        'Type de Test': test.test_type,
        'Norme ISO': test.iso_standard or '',
        'Technicien': test.technician.username,
        'Longueur (mm)': test.length if test.length else '',
        'Largeur (mm)': test.width if test.width else '',
        'Épaisseur (mm)': test.thickness if test.thickness else '',
        'Gauchissement (mm)': test.warping if test.warping else '',
        'Absorption d\'eau (%)': test.water_absorption if test.water_absorption else '',
        'Résistance rupture (N/mm²)': test.breaking_strength if test.breaking_strength else '',
        'Résistance abrasion': test.abrasion_resistance if test.abrasion_resistance else '',
        'Score de Conformité (%)': test.compliance_score if test.compliance_score else '',
        'Résultat': 'Conforme' if test.result == 'pass' else 'Non conforme',
        'Défauts visuels': test.visual_defects if test.visual_defects else '',
        'Notes': test.notes if test.notes else ''
    }]
    
    df = pd.DataFrame(data)
    
    # Create Excel file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Test Détaillé', index=False)
        
        workbook = writer.book
        worksheet = writer.sheets['Test Détaillé']
        
        # Auto-adjust column widths
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    output.seek(0)
    
    return send_file(
        output,
        as_attachment=True,
        download_name=f'test_detaille_{test.batch.lot_number}_{test.test_date.strftime("%Y%m%d")}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

def generate_production_pdf_report(batches):
    """Generate PDF report for production batches"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    elements = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#2c3e50')
    )
    
    # Title
    title = Paragraph("RAPPORT DE PRODUCTION", title_style)
    elements.append(title)
    
    # Header info
    header_info = Paragraph(
        f"<b>CERAMICA DERS</b><br/>"
        f"Date d'édition: {datetime.now().strftime('%d/%m/%Y')}<br/>"
        f"Nombre de lots: {len(batches)}",
        styles['Normal']
    )
    elements.append(header_info)
    elements.append(Spacer(1, 20))
    
    if batches:
        # Table data
        data = [['N° Lot', 'Produit', 'Quantité Prévue', 'Quantité Réelle', 'Date', 'Four', 'Statut']]
        
        for batch in batches:
            data.append([
                batch.lot_number,
                batch.product_type,
                str(batch.planned_quantity),
                str(batch.actual_quantity),
                batch.production_date.strftime('%d/%m/%Y'),
                batch.kiln_number,
                batch.status
            ])
        
        table = Table(data, colWidths=[1.2*inch, 1.3*inch, 0.9*inch, 0.9*inch, 1*inch, 0.8*inch, 1*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(table)
    else:
        no_data = Paragraph("Aucun lot de production trouvé.", styles['Normal'])
        elements.append(no_data)
    
    doc.build(elements)
    buffer.seek(0)
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f'rapport_production_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf',
        mimetype='application/pdf'
    )

def generate_production_excel_report(batches):
    """Generate Excel report for production batches"""
    data = []
    for batch in batches:
        data.append({
            'Numéro de Lot': batch.lot_number,
            'Type de Produit': batch.product_type,
            'Quantité Prévue': batch.planned_quantity,
            'Quantité Réelle': batch.actual_quantity,
            'Date de Production': batch.production_date.strftime('%d/%m/%Y'),
            'Numéro de Four': batch.kiln_number,
            'Température (°C)': batch.kiln_temperature if batch.kiln_temperature else '',
            'Durée de Cuisson (h)': batch.firing_duration if batch.firing_duration else '',
            'Statut': batch.status,
            'Superviseur': batch.supervisor.username if batch.supervisor else '',
            'Date de Création': batch.created_at.strftime('%d/%m/%Y'),
            'Notes': batch.notes if batch.notes else ''
        })
    
    df = pd.DataFrame(data)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Production', index=False)
        
        workbook = writer.book
        worksheet = writer.sheets['Production']
        
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    output.seek(0)
    
    return send_file(
        output,
        as_attachment=True,
        download_name=f'rapport_production_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

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
