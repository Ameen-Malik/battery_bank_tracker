from datetime import datetime

def format_duration(start_time, end_time):
    if not end_time:
        return "In Progress"
    duration = end_time - start_time
    hours = duration.seconds // 3600
    minutes = (duration.seconds % 3600) // 60
    return f"{hours}h {minutes}m"

def get_test_progress(test):
    total_phases = test.total_cycles * 2  # Each cycle has charge and discharge
    completed_phases = (test.current_cycle - 1) * 2
    if test.current_phase == 'discharge':
        completed_phases += 1
    return (completed_phases / total_phases) * 100
