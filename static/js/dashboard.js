document.addEventListener('DOMContentLoaded', function() {
    
    // Helper function to easily grab and parse data from our HTML bridge
    const getChartData = (id) => JSON.parse(document.getElementById(id).textContent);

    // --- 1. ATTENDANCE BAR CHART ---
    const attendanceCtx = document.getElementById('attendanceChart').getContext('2d');
    new Chart(attendanceCtx, {
        type: 'bar',
        data: { 
            labels: getChartData('attendanceLabels'), 
            datasets: [{ 
                label: 'Check-ins', 
                data: getChartData('attendanceData'), 
                backgroundColor: '#4f46e5', 
                borderRadius: 4 
            }] 
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
    });

    // --- 2. APPROVAL PIE CHART ---
    const approvalCtx = document.getElementById('approvalChart').getContext('2d');
    new Chart(approvalCtx, {
        type: 'pie',
        data: { 
            labels: getChartData('approvalLabels'), 
            datasets: [{ 
                data: getChartData('approvalData'), 
                backgroundColor: ['#22c55e', '#f59e0b'], 
                borderWidth: 0 
            }] 
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
    });

    // --- 3. LEAVE REQUESTS DOUGHNUT CHART ---
    const leaveCtx = document.getElementById('leaveChart').getContext('2d');
    new Chart(leaveCtx, {
        type: 'doughnut',
        data: { 
            labels: getChartData('leaveLabels'), 
            datasets: [{ 
                data: getChartData('leaveData'), 
                backgroundColor: ['#22c55e', '#ef4444', '#eab308'], 
                borderWidth: 0 
            }] 
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
    });

});