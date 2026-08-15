document.addEventListener('DOMContentLoaded', () => {
    const getChartData = (id) => {
        const element = document.getElementById(id);
        return element ? JSON.parse(element.textContent) : [];
    };

    const attendanceCanvas = document.getElementById('attendanceChart');
    const approvalCanvas = document.getElementById('approvalChart');
    const leaveCanvas = document.getElementById('leaveChart');

    if (typeof Chart === 'undefined' || !attendanceCanvas || !approvalCanvas || !leaveCanvas) {
        return;
    }

    new Chart(attendanceCanvas, {
        type: 'bar',
        data: {
            labels: getChartData('attendanceLabels'),
            datasets: [{
                label: 'Check-ins',
                data: getChartData('attendanceData'),
                backgroundColor: '#4f46e5',
                borderRadius: 4,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {legend: {display: false}},
        },
    });

    new Chart(approvalCanvas, {
        type: 'pie',
        data: {
            labels: getChartData('approvalLabels'),
            datasets: [{
                data: getChartData('approvalData'),
                backgroundColor: ['#22c55e', '#f59e0b'],
                borderWidth: 0,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {legend: {position: 'bottom'}},
        },
    });

    new Chart(leaveCanvas, {
        type: 'doughnut',
        data: {
            labels: getChartData('leaveLabels'),
            datasets: [{
                data: getChartData('leaveData'),
                backgroundColor: ['#22c55e', '#ef4444', '#eab308'],
                borderWidth: 0,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {legend: {position: 'bottom'}},
        },
    });
});
