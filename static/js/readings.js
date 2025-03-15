let isOCV = true;
let intervalTimer = null;
let ccvSequence = 0;

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('readingsForm');
    const endPhaseBtn = document.getElementById('endPhase');
    const readingsLog = document.getElementById('readingsLog');
    const intervalModal = new bootstrap.Modal(document.getElementById('intervalModal'));
    
    updatePhaseDisplay();
    
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const readings = [];
        document.querySelectorAll('.reading-input').forEach(input => {
            readings.push(parseFloat(input.value));
        });
        
        if (isOCV) {
            await submitOCVReadings(readings);
        } else {
            await submitCCVReadings(readings);
        }
    });
    
    endPhaseBtn.addEventListener('click', async function() {
        if (confirm('Are you sure you want to end the current phase?')) {
            await endCurrentPhase();
        }
    });
    
    function updatePhaseDisplay() {
        document.getElementById('currentPhase').textContent = currentPhase.charAt(0).toUpperCase() + currentPhase.slice(1);
        document.getElementById('readingType').textContent = isOCV ? 'OCV' : 'CCV';
        document.getElementById('timeIntervalSection').style.display = isOCV ? 'block' : 'none';
        endPhaseBtn.style.display = isOCV ? 'none' : 'block';
    }
    
    async function submitOCVReadings(readings) {
        try {
            const response = await fetch(`/api/tests/${testId}/ocv`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ readings })
            });
            
            if (response.ok) {
                const ccvInterval = document.getElementById('ccvInterval').value;
                isOCV = false;
                ccvSequence = 0;
                updatePhaseDisplay();
                clearForm();
                logReading('OCV readings submitted successfully');
                
                // Start interval timer for CCV readings
                startCCVInterval(parseInt(ccvInterval));
            }
        } catch (error) {
            console.error('Error submitting OCV readings:', error);
            showAlert('Failed to submit OCV readings');
        }
    }
    
    async function submitCCVReadings(readings) {
        try {
            const response = await fetch(`/api/tests/${testId}/ccv`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ readings })
            });
            
            if (response.ok) {
                ccvSequence++;
                clearForm();
                logReading(`CCV readings #${ccvSequence} submitted successfully`);
            }
        } catch (error) {
            console.error('Error submitting CCV readings:', error);
            showAlert('Failed to submit CCV readings');
        }
    }
    
    async function endCurrentPhase() {
        try {
            const response = await fetch(`/api/tests/${testId}/end-phase`, {
                method: 'POST'
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    clearInterval(intervalTimer);
                    isOCV = true;
                    
                    if (data.test_completed) {
                        window.location.href = '/';
                    } else {
                        updatePhaseDisplay();
                        clearForm();
                        logReading('Phase completed. Starting new phase with OCV readings.');
                    }
                }
            }
        } catch (error) {
            console.error('Error ending phase:', error);
            showAlert('Failed to end the current phase');
        }
    }
    
    function startCCVInterval(interval) {
        intervalTimer = setInterval(() => {
            intervalModal.show();
        }, interval * 1000);
    }
    
    function clearForm() {
        document.querySelectorAll('.reading-input').forEach(input => {
            input.value = '';
        });
    }
    
    function logReading(message) {
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = document.createElement('div');
        logEntry.className = 'log-entry';
        logEntry.innerHTML = `<strong>${timestamp}</strong>: ${message}`;
        readingsLog.insertBefore(logEntry, readingsLog.firstChild);
    }
});
