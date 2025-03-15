from flask import Blueprint, render_template, request, jsonify, send_file
from datetime import datetime
import pandas as pd
from io import StringIO
from io import BytesIO # Added for binary mode handling
from models import db, BatteryBank, TestSession, ReadingCycle, Reading
from utils import format_duration, get_test_progress

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def dashboard():
    tests = TestSession.query.all()
    return render_template('dashboard.html', tests=tests, get_test_progress=get_test_progress)

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
    return render_template('test_details.html', test=test, format_duration=format_duration)

@main_bp.route('/test/<int:test_id>/readings')
def take_readings(test_id):
    test = TestSession.query.get_or_404(test_id)
    return render_template('take_readings.html', test=test)

@main_bp.route('/api/tests/<int:test_id>/ocv', methods=['POST'])
def submit_ocv(test_id):
    data = request.json
    test = TestSession.query.get_or_404(test_id)

    # Create new reading cycle
    cycle = ReadingCycle(
        test_id=test_id,
        cycle_number=test.current_cycle,
        phase=test.current_phase
    )
    db.session.add(cycle)
    db.session.flush()

    # Add OCV readings
    for cell_num, value in enumerate(data['readings'], 1):
        reading = Reading(
            cycle_id=cycle.id,
            reading_type='OCV',
            cell_number=cell_num,
            value=float(value),
            phase=test.current_phase
        )
        db.session.add(reading)

    # Update test status to in_progress if this is the first reading
    if test.status == 'scheduled':
        test.status = 'in_progress'

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

    sequence = len(current_cycle.get_readings_by_type('CCV')) // test.bank.num_cells + 1

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
    return jsonify({'success': True, 'test_completed': test.status == 'completed'})

@main_bp.route('/api/tests/<int:test_id>/export')
def export_csv(test_id):
    test = TestSession.query.get_or_404(test_id)

    # Prepare data for each cycle
    export_data = []
    for cycle in test.cycles:
        # Get all unique CCV sequence numbers for this cycle
        ccv_readings = sorted(
            (r for r in cycle.readings if r.reading_type == 'CCV'),
            key=lambda x: x.sequence_number
        )
        ccv_sequences = sorted(set(r.sequence_number for r in ccv_readings))

        # Create rows for each cell
        for cell_num in range(1, test.bank.num_cells + 1):
            row = {
                'Cycle': cycle.cycle_number,
                'Phase': cycle.phase.capitalize(),
                'Cell No.': cell_num,
                'OCV': next((r.value for r in cycle.readings 
                           if r.reading_type == 'OCV' and r.cell_number == cell_num), None)
            }

            # Add CCV readings with timestamps
            for seq in ccv_sequences:
                ccv = next((r for r in ccv_readings 
                          if r.sequence_number == seq and r.cell_number == cell_num), None)
                if ccv:
                    row[f'CCV-{seq} ({ccv.timestamp.strftime("%I:%M %p")})'] = ccv.value
                else:
                    row[f'CCV-{seq}'] = None

            export_data.append(row)

    # Convert to DataFrame and format
    df = pd.DataFrame(export_data)
    df = df.sort_values(['Cycle', 'Phase', 'Cell No.'])

    # Export to CSV in binary mode
    output = StringIO()
    df.to_csv(output, index=False)
    output.seek(0)

    return send_file(
        BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'test_{test_id}_export.csv'
    )