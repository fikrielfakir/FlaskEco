// EcoQuality Application JavaScript

// DOM Content Loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    initializeTooltips();
    
    // Initialize form validations
    initializeFormValidation();
    
    // Initialize auto-refresh for dashboards
    initializeAutoRefresh();
    
    // Initialize search functionality
    initializeSearch();
    
    // Initialize confirmation dialogs
    initializeConfirmations();
});

// Initialize Bootstrap tooltips
function initializeTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Form validation enhancements
function initializeFormValidation() {
    const forms = document.querySelectorAll('.needs-validation');
    
    Array.prototype.slice.call(forms).forEach(function(form) {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            
            form.classList.add('was-validated');
        }, false);
    });
    
    // Real-time validation for specific fields
    setupRealTimeValidation();
}

// Real-time validation for form fields
function setupRealTimeValidation() {
    // Quantity validation
    const quantityInputs = document.querySelectorAll('input[name*="quantity"]');
    quantityInputs.forEach(input => {
        input.addEventListener('input', function() {
            const value = parseFloat(this.value);
            if (value < 0) {
                this.setCustomValidity('La quantité ne peut pas être négative');
            } else {
                this.setCustomValidity('');
            }
        });
    });
    
    // Temperature validation for kilns
    const tempInputs = document.querySelectorAll('input[name="kiln_temperature"]');
    tempInputs.forEach(input => {
        input.addEventListener('input', function() {
            const value = parseFloat(this.value);
            if (value && (value < 800 || value > 1400)) {
                this.setCustomValidity('La température doit être entre 800°C et 1400°C');
            } else {
                this.setCustomValidity('');
            }
        });
    });
    
    // Percentage validation
    const percentageInputs = document.querySelectorAll('input[name*="percentage"], input[name*="efficiency"]');
    percentageInputs.forEach(input => {
        input.addEventListener('input', function() {
            const value = parseFloat(this.value);
            if (value < 0 || value > 100) {
                this.setCustomValidity('Le pourcentage doit être entre 0 et 100');
            } else {
                this.setCustomValidity('');
            }
        });
    });
}

// Auto-refresh dashboard data
function initializeAutoRefresh() {
    const dashboardPage = document.querySelector('.dashboard-page');
    if (dashboardPage) {
        // Refresh every 5 minutes
        setInterval(function() {
            if (document.visibilityState === 'visible') {
                refreshDashboardStats();
            }
        }, 300000);
    }
}

// Refresh dashboard statistics
function refreshDashboardStats() {
    const statsCards = document.querySelectorAll('.stat-card');
    
    // Add loading state
    statsCards.forEach(card => {
        card.classList.add('loading');
    });
    
    // Simulate API call (replace with actual implementation if needed)
    setTimeout(() => {
        statsCards.forEach(card => {
            card.classList.remove('loading');
        });
    }, 1000);
}

// Enhanced search functionality
function initializeSearch() {
    const searchInputs = document.querySelectorAll('input[name="search"]');
    
    searchInputs.forEach(input => {
        let searchTimeout;
        
        input.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            const searchTerm = this.value.trim();
            
            if (searchTerm.length >= 2) {
                searchTimeout = setTimeout(() => {
                    performSearch(searchTerm, this);
                }, 300);
            }
        });
    });
}

// Perform search with highlight
function performSearch(term, inputElement) {
    const form = inputElement.closest('form');
    if (!form) return;
    
    // Auto-submit form for server-side filtering
    if (term.length >= 3) {
        form.submit();
    }
}

// Confirmation dialogs for destructive actions
function initializeConfirmations() {
    const dangerousActions = document.querySelectorAll('[data-confirm]');
    
    dangerousActions.forEach(element => {
        element.addEventListener('click', function(event) {
            const message = this.getAttribute('data-confirm');
            if (!confirm(message)) {
                event.preventDefault();
                return false;
            }
        });
    });
}

// Utility functions
const Utils = {
    // Format numbers with proper localization
    formatNumber: function(number, decimals = 1) {
        return new Intl.NumberFormat('fr-FR', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        }).format(number);
    },
    
    // Format currency
    formatCurrency: function(amount) {
        return new Intl.NumberFormat('fr-FR', {
            style: 'currency',
            currency: 'MAD'
        }).format(amount);
    },
    
    // Format dates
    formatDate: function(date) {
        return new Intl.DateTimeFormat('fr-FR').format(new Date(date));
    },
    
    // Show toast notifications
    showToast: function(message, type = 'info') {
        const toastContainer = document.querySelector('.toast-container') || createToastContainer();
        const toast = createToast(message, type);
        toastContainer.appendChild(toast);
        
        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();
        
        // Remove toast after it's hidden
        toast.addEventListener('hidden.bs.toast', function() {
            toast.remove();
        });
    },
    
    // Loading states
    setLoading: function(element, loading = true) {
        if (loading) {
            element.classList.add('loading');
            element.disabled = true;
        } else {
            element.classList.remove('loading');
            element.disabled = false;
        }
    }
};

// Create toast container if it doesn't exist
function createToastContainer() {
    const container = document.createElement('div');
    container.className = 'toast-container position-fixed top-0 end-0 p-3';
    container.style.zIndex = '9999';
    document.body.appendChild(container);
    return container;
}

// Create toast element
function createToast(message, type) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.setAttribute('role', 'alert');
    
    const iconMap = {
        success: 'fas fa-check-circle text-success',
        error: 'fas fa-exclamation-circle text-danger',
        warning: 'fas fa-exclamation-triangle text-warning',
        info: 'fas fa-info-circle text-info'
    };
    
    toast.innerHTML = `
        <div class="toast-header">
            <i class="${iconMap[type] || iconMap.info} me-2"></i>
            <strong class="me-auto">EcoQuality</strong>
            <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
        </div>
        <div class="toast-body">
            ${message}
        </div>
    `;
    
    return toast;
}

// Chart initialization (if Chart.js is loaded)
function initializeCharts() {
    if (typeof Chart === 'undefined') return;
    
    // Energy consumption chart
    const energyCtx = document.getElementById('energyChart');
    if (energyCtx) {
        new Chart(energyCtx, {
            type: 'doughnut',
            data: {
                labels: ['Électricité', 'Gaz', 'Solaire'],
                datasets: [{
                    data: [0, 0, 0], // Will be populated with real data
                    backgroundColor: [
                        'var(--bs-primary)',
                        'var(--bs-warning)',
                        'var(--bs-success)'
                    ]
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }
    
    // Quality trends chart
    const qualityCtx = document.getElementById('qualityChart');
    if (qualityCtx) {
        new Chart(qualityCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Taux de Conformité',
                    data: [],
                    borderColor: 'var(--bs-success)',
                    backgroundColor: 'rgba(var(--bs-success-rgb), 0.1)',
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            callback: function(value) {
                                return value + '%';
                            }
                        }
                    }
                }
            }
        });
    }
}

// Keyboard shortcuts
document.addEventListener('keydown', function(event) {
    // Ctrl/Cmd + K for search focus
    if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
        event.preventDefault();
        const searchInput = document.querySelector('input[name="search"]');
        if (searchInput) {
            searchInput.focus();
        }
    }
    
    // Escape to close modals
    if (event.key === 'Escape') {
        const openModal = document.querySelector('.modal.show');
        if (openModal) {
            const modal = bootstrap.Modal.getInstance(openModal);
            if (modal) modal.hide();
        }
    }
});

// Export utilities for global use
window.EcoQuality = {
    Utils: Utils,
    initializeCharts: initializeCharts,
    showToast: Utils.showToast
};

// Auto-save form data to localStorage
function initializeAutoSave() {
    const forms = document.querySelectorAll('form[data-autosave]');
    
    forms.forEach(form => {
        const formId = form.getAttribute('data-autosave');
        
        // Load saved data
        const savedData = localStorage.getItem(`autosave_${formId}`);
        if (savedData) {
            try {
                const data = JSON.parse(savedData);
                Object.keys(data).forEach(key => {
                    const input = form.querySelector(`[name="${key}"]`);
                    if (input && input.type !== 'password') {
                        input.value = data[key];
                    }
                });
            } catch (e) {
                console.warn('Failed to load autosave data:', e);
            }
        }
        
        // Save data on input
        form.addEventListener('input', debounce(function() {
            const formData = new FormData(form);
            const data = {};
            
            for (let [key, value] of formData.entries()) {
                if (form.querySelector(`[name="${key}"]`).type !== 'password') {
                    data[key] = value;
                }
            }
            
            localStorage.setItem(`autosave_${formId}`, JSON.stringify(data));
        }, 1000));
        
        // Clear autosave on successful submit
        form.addEventListener('submit', function() {
            localStorage.removeItem(`autosave_${formId}`);
        });
    });
}

// Debounce utility
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Initialize autosave when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeAutoSave);
} else {
    initializeAutoSave();
}
