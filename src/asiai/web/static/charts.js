/* asiai web dashboard — ApexCharts dark config and chart factories */

const COLORS = {
    blue: '#3b82f6',
    cyan: '#06b6d4',
    green: '#22c55e',
    yellow: '#eab308',
    red: '#ef4444',
    purple: '#a855f7',
    orange: '#f97316',
};

const ENGINE_COLORS = {
    ollama: COLORS.blue,
    lmstudio: COLORS.cyan,
    mlxlm: COLORS.green,
    llamacpp: COLORS.yellow,
    vllm_mlx: COLORS.purple,
};

function isLightTheme() {
    return document.documentElement.getAttribute('data-theme') === 'light';
}

function getChartTheme() {
    var light = isLightTheme();
    return {
        chart: {
            background: 'transparent',
            foreColor: light ? '#525252' : '#a3a3a3',
            fontFamily: 'Inter, system-ui, sans-serif',
            toolbar: { show: false },
            animations: {
                enabled: true,
                easing: 'easeinout',
                speed: 600,
            },
        },
        grid: {
            borderColor: light ? '#e5e5e5' : '#262626',
            strokeDashArray: 4,
        },
        tooltip: {
            theme: light ? 'light' : 'dark',
            style: { fontFamily: 'JetBrains Mono, monospace', fontSize: '12px' },
        },
        xaxis: {
            axisBorder: { color: light ? '#e5e5e5' : '#262626' },
            axisTicks: { color: light ? '#e5e5e5' : '#262626' },
            labels: { style: { colors: light ? '#525252' : '#737373', fontSize: '11px' } },
        },
        yaxis: {
            labels: { style: { colors: light ? '#525252' : '#737373', fontSize: '11px' } },
        },
    };
}

// Backward compat alias
var DARK_THEME = getChartTheme();

function mergeOptions(base, override) {
    const result = {};
    for (const key of Object.keys(base)) {
        if (typeof base[key] === 'object' && !Array.isArray(base[key]) && base[key] !== null) {
            result[key] = mergeOptions(base[key], override[key] || {});
        } else {
            result[key] = override[key] !== undefined ? override[key] : base[key];
        }
    }
    for (const key of Object.keys(override)) {
        if (!(key in result)) {
            result[key] = override[key];
        }
    }
    return result;
}

/**
 * Create a horizontal bar chart (tok/s comparison).
 */
function createBarChart(elementId, categories, values, opts = {}) {
    const colors = categories.map(c => ENGINE_COLORS[c] || COLORS.blue);
    const options = mergeOptions(getChartTheme(), {
        chart: { type: 'bar', height: opts.height || 250 },
        series: [{ name: opts.label || 'Value', data: values }],
        plotOptions: {
            bar: {
                horizontal: true,
                borderRadius: 4,
                barHeight: '60%',
                distributed: true,
            },
        },
        colors: colors,
        xaxis: { categories: categories },
        yaxis: {
            labels: {
                style: {
                    fontFamily: 'JetBrains Mono, monospace',
                    fontSize: '13px',
                    colors: isLightTheme() ? '#171717' : '#fafafa',
                },
            },
        },
        legend: { show: false },
        dataLabels: {
            enabled: true,
            style: {
                fontFamily: 'JetBrains Mono, monospace',
                fontSize: '12px',
            },
            formatter: (val) => opts.unit ? `${val.toFixed(1)} ${opts.unit}` : val.toFixed(1),
        },
    });

    const chart = new ApexCharts(document.querySelector(`#${elementId}`), options);
    chart.render();
    return chart;
}

/**
 * Create a time series line chart.
 */
function createTimeChart(elementId, seriesData, opts = {}) {
    const options = mergeOptions(getChartTheme(), {
        chart: { type: 'line', height: opts.height || 300 },
        series: seriesData,
        stroke: { width: 2, curve: 'smooth' },
        colors: seriesData.map((s, i) =>
            ENGINE_COLORS[s.name] || Object.values(COLORS)[i % Object.values(COLORS).length]
        ),
        xaxis: {
            type: 'datetime',
            labels: {
                datetimeUTC: false,
                style: { colors: isLightTheme() ? '#525252' : '#737373', fontSize: '11px' },
            },
        },
        yaxis: {
            title: { text: opts.yTitle || '', style: { color: isLightTheme() ? '#525252' : '#737373' } },
            labels: {
                style: { colors: isLightTheme() ? '#525252' : '#737373', fontSize: '11px' },
                formatter: opts.yFormatter || ((v) => v.toFixed(1)),
            },
        },
        legend: {
            position: 'top',
            horizontalAlign: 'left',
            labels: { colors: isLightTheme() ? '#525252' : '#a3a3a3' },
        },
    });

    const chart = new ApexCharts(document.querySelector(`#${elementId}`), options);
    chart.render();
    return chart;
}

/**
 * Create a radial gauge (for memory / CPU).
 */
function createGauge(elementId, value, opts = {}) {
    const color = value > 90 ? COLORS.red : value > 70 ? COLORS.yellow : COLORS.blue;
    const options = {
        chart: {
            type: 'radialBar',
            height: opts.height || 180,
            background: 'transparent',
            fontFamily: 'Inter, system-ui, sans-serif',
        },
        series: [Math.round(value)],
        plotOptions: {
            radialBar: {
                hollow: { size: '60%' },
                track: { background: isLightTheme() ? '#e5e5e5' : '#262626' },
                dataLabels: {
                    name: {
                        show: true,
                        color: '#737373',
                        fontSize: '11px',
                        offsetY: 15,
                    },
                    value: {
                        show: true,
                        color: isLightTheme() ? '#171717' : '#fafafa',
                        fontFamily: 'JetBrains Mono, monospace',
                        fontSize: '20px',
                        fontWeight: 700,
                        offsetY: -10,
                        formatter: (val) => `${val}%`,
                    },
                },
            },
        },
        colors: [color],
        labels: [opts.label || ''],
    };

    const chart = new ApexCharts(document.querySelector(`#${elementId}`), options);
    chart.render();
    return chart;
}

/**
 * Create a sparkline chart.
 */
function createSparkline(elementId, data, opts = {}) {
    const options = {
        chart: {
            type: 'area',
            height: opts.height || 60,
            sparkline: { enabled: true },
            background: 'transparent',
        },
        series: [{ data: data }],
        stroke: { width: 1.5, curve: 'smooth' },
        fill: {
            type: 'gradient',
            gradient: {
                shadeIntensity: 1,
                opacityFrom: 0.3,
                opacityTo: 0.05,
            },
        },
        colors: [opts.color || COLORS.blue],
        tooltip: {
            theme: isLightTheme() ? 'light' : 'dark',
            fixed: { enabled: false },
            y: {
                formatter: opts.formatter || ((v) => v.toFixed(1)),
            },
        },
    };

    const chart = new ApexCharts(document.querySelector(`#${elementId}`), options);
    chart.render();
    return chart;
}

/**
 * Format bytes to human-readable.
 */
function formatBytes(n) {
    if (n <= 0) return '—';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    while (n >= 1024 && i < units.length - 1) {
        n /= 1024;
        i++;
    }
    return `${n.toFixed(1)} ${units[i]}`;
}

/**
 * Format uptime seconds to human-readable.
 */
function formatUptime(seconds) {
    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    if (d > 0) return `${d}d ${h}h`;
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
}
