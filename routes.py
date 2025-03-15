from flask import Blueprint, render_template, request, jsonify, send_file
from datetime import datetime
import pandas as pd
from io import StringIO
from models import db, BatteryBank, TestSession, ReadingCycle, Reading

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def dashboard():
    tests = TestSession.query.all()
    return render_template('dashboard.html', tests=tests)

@main_bp.route('/create_test', methods=['GET', 'POST'])
def create_test():
    if request.method == 'POST':
        bank = BatteryBank(
            name=request.form['name'],
            description=request.form['description'],
            num_cells=int(request.form['num_cells'])
        )
        db.session.add(bank)
        db.session.flush()
        
        test = TestSession(
            bank_id=bank.id,
            total_cycles=int(request.form['total_cycles'])
        )
        db.session.add(test)
        db.session.commit()
        return jsonify({'success': True, 'test_id': test.id})
    
    return render_template('create_test.html')

@main_bp.route('/test/<int:test_id>')
def test_details(test_id):
    test = TestSession.query.get_or_404(test_id)
    return render_template('test_details.html', test=test)

@main_bp.route('/test/<int:test_id>/readings')
def take_readings(test_id):
    test = TestSession.query.get_or_404(test_id)
    return render_template('take_readings.html', test=test)

@main_bp.route('/api/tests/<int:test_id>/ocv', methods=['POST'])
def submit_ocv(test_id):
    data = request.json
    test = TestSession.query.get_or_404(test_id)
    
    cycle = ReadingCycle(
        test_id=test_id,
        cycle_number=test.current_cycle,
        phase=test.current_phase
    )
    db.session.add(cycle)
    db.session.flush()
    
    for cell_num, value in enumerate(data['readings'], 1):
        reading = Reading(
            cycle_id=cycle.id,
            reading_type='OCV',
            cell_number=cell_num,
            value=float(value),
            phase=test.current_phase
        )
        db.session.add(reading)
    
    db.session.commit()
    return jsonify({'success': True})

@main_bp.route('/api/tests/<int:test_id>/ccv', methods=['POST'])
def submit_ccv(test_id):
    data = request.json
    test = TestSession.query.get_or_404(test_id)
    current_cycle = ReadingCycle.query.filter_by(
        test_id=test_id,
        cycle_number=test.current_cycle,
        phase=test.current_phase,
        status='active'
    ).first()
    
    sequence = len(current_cycle.readings.filter_by(reading_type='CCV').all()) + 1
    
    for cell_num, value in enumerate(data['readings'], 1):
        reading = Reading(
            cycle_id=current_cycle.id,
            reading_type='CCV',
            cell_number=cell_num,
            value=float(value),
            sequence_number=sequence,
            phase=test.current_phase
        )
        db.session.add(reading)
    
    db.session.commit()
    return jsonify({'success': True})

@main_bp.route('/api/tests/<int:test_id>/end-phase', methods=['POST'])
def end_phase(test_id):
    test = TestSession.query.get_or_404(test_id)
    current_cycle = ReadingCycle.query.filter_by(
        test_id=test_id,
        cycle_number=test.current_cycle,
        phase=test.current_phase,
        status='active'
    ).first()
    
    current_cycle.status = 'completed'
    current_cycle.end_time = datetime.utcnow()
    
    if test.current_phase == 'charge':
        test.current_phase = 'discharge'
    else:
        test.current_phase = 'charge'
        test.current_cycle += 1
        
    if test.current_cycle > test.total_cycles:
        test.status = 'completed'
    
    db.session.commit()
    return jsonify({'success': True})

@main_bp.route('/api/tests/<int:test_id>/export')
def export_csv(test_id):
    test = TestSession.query.get_or_404(test_id)
    
    # Create DataFrame for export
    data = []
    for cycle in test.cycles:
        cycle_data = {
            'Cycle': cycle.cycle_number,
            'Phase': cycle.phase.capitalize(),
            'Start Time': cycle.start_time,
            'End Time': cycle.end_time
        }
        
        ocv_readings = {r.cell_number: r.value for r in cycle.readings if r.reading_type == 'OCV'}
        ccv_readings = {}
        for r in cycle.readings:
            if r.reading_type == 'CCV':
                key = f'CCV-{r.sequence_number}-Cell-{r.cell_number}'
                ccv_readings[key] = r.value
        
        cycle_data.update({f'OCV-Cell-{i}': ocv_readings.get(i) for i in range(1, test.bank.num_cells + 1)})
        cycle_data.update(ccv_readings)
        data.append(cycle_data)
    
    df = pd.DataFrame(data)
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)
    
    return send_file(
        StringIO(csv_buffer.getvalue()),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'test_{test_id}_export.csv'
    )
