from flask import Blueprint, render_template, request, jsonify, send_file
from datetime import datetime
import pandas as pd
from io import StringIO, BytesIO
from weasyprint import HTML, CSS
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
    export_data = []

    for cycle in test.cycles:
        # Get all CCV readings for this cycle
        ccv_readings = cycle.get_readings_by_type('CCV')
        ccv_sequences = sorted(set(r.sequence_number for r in ccv_readings))

        # Prepare data for each cell
        for cell_num in range(1, test.bank.num_cells + 1):
            row = {
                'Cycle': cycle.cycle_number,
                'Phase': cycle.phase.capitalize(),
                'Cell No.': cell_num
            }

            # Add OCV reading
            ocv = next((r for r in cycle.readings 
                       if r.reading_type == 'OCV' and r.cell_number == cell_num), None)
            row['OCV'] = f"{ocv.value:.2f}" if ocv else '-'

            # Add CCV readings with timestamps
            for seq in ccv_sequences:
                ccv = next((r for r in ccv_readings 
                          if r.sequence_number == seq and r.cell_number == cell_num), None)
                header = f"CCV-{seq} ({ccv.timestamp.strftime('%I:%M %p') if ccv else ''})"
                row[header] = f"{ccv.value:.2f}" if ccv else '-'

            export_data.append(row)

    # Create DataFrame and sort
    df = pd.DataFrame(export_data)
    df = df.sort_values(['Cycle', 'Phase', 'Cell No.'])

    # Export to CSV
    output = StringIO()
    df.to_csv(output, index=False)
    output.seek(0)

    return send_file(
        BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'test_{test_id}_export.csv'
    )

@main_bp.route('/api/tests/<int:test_id>/export/pdf')
def export_pdf(test_id):
    test = TestSession.query.get_or_404(test_id)

    # Generate HTML content using the same template as test details
    html_content = render_template(
        'test_details.html', 
        test=test,
        format_duration=format_duration,
        export_mode=True
    )

    # Define CSS for PDF export
    css = CSS(string='''
        @page { size: A4; margin: 2cm }
        body { font-family: Arial, sans-serif; }
        .card { margin-bottom: 20px; border: 1px solid #ddd; padding: 15px; }
        .card-header { background-color: #f8f9fa; padding: 10px; margin-bottom: 15px; }
        .table { width: 100%; border-collapse: collapse; margin-bottom: 15px; }
        .table th, .table td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        .table th { background-color: #f8f9fa; }
        .badge { padding: 5px 10px; border-radius: 4px; }
        .text-muted { color: #6c757d; }
    ''')

    # Convert HTML to PDF with custom CSS
    pdf = HTML(string=html_content).write_pdf(stylesheets=[css])

    return send_file(
        BytesIO(pdf),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'test_{test_id}_report.pdf'
    )