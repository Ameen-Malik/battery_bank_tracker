from datetime import datetime
from app import db

class BatteryBank(db.Model):
    __tablename__ = 'battery_banks'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    num_cells = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    tests = db.relationship('TestSession', backref='bank', lazy=True)

class TestSession(db.Model):
    __tablename__ = 'test_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    bank_id = db.Column(db.Integer, db.ForeignKey('battery_banks.id'), nullable=False)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='active')  # active, completed, aborted
    total_cycles = db.Column(db.Integer, nullable=False)
    current_cycle = db.Column(db.Integer, default=1)
    current_phase = db.Column(db.String(20), default='charge')  # charge, discharge
    cycles = db.relationship('ReadingCycle', backref='test', lazy=True)

class ReadingCycle(db.Model):
    __tablename__ = 'reading_cycles'
    
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('test_sessions.id'), nullable=False)
    cycle_number = db.Column(db.Integer, nullable=False)
    phase = db.Column(db.String(20), nullable=False)  # charge, discharge
    ccv_interval = db.Column(db.Integer)  # interval in seconds
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='active')  # active, completed
    readings = db.relationship('Reading', backref='cycle', lazy=True)

class Reading(db.Model):
    __tablename__ = 'readings'
    
    id = db.Column(db.Integer, primary_key=True)
    cycle_id = db.Column(db.Integer, db.ForeignKey('reading_cycles.id'), nullable=False)
    reading_type = db.Column(db.String(3), nullable=False)  # OCV, CCV
    cell_number = db.Column(db.Integer, nullable=False)
    value = db.Column(db.Float, nullable=False)
    sequence_number = db.Column(db.Integer)  # For CCV readings
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    phase = db.Column(db.String(20), nullable=False)  # charge, discharge
