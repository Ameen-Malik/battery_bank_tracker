// Common utility functions
function showAlert(message, type = 'danger') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    const container = document.querySelector('.container');
    container.insertBefore(alertDiv, container.firstChild);
    
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

function formatDateTime(date) {
    return new Date(date).toLocaleString();
}

function validateNumericInput(input) {
    input.addEventListener('input', function(e) {
        if (isNaN(e.target.value)) {
            e.target.value = '';
        }
    });
}

// Initialize all numeric inputs
document.addEventListener('DOMContentLoaded', function() {
    const numericInputs = document.querySelectorAll('input[type="number"]');
    numericInputs.forEach(validateNumericInput);
});

// Handle form submissions
async function handleFormSubmit(url, formData, successCallback) {
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        if (data.success) {
            successCallback(data);
        } else {
            showAlert(data.message || 'Operation failed. Please try again.');
        }
    } catch (error) {
        console.error('Error:', error);
        showAlert('An error occurred while processing your request.');
    }
}

// Export handling
function handleExport(testId) {
    window.location.href = `/api/tests/${testId}/export`;
}
